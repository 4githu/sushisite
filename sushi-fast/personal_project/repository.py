import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import stat
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from . import attachment_cleanup
from .academic import (
    LEGACY_STAGE_ALIASES,
    STAGE_LABELS,
    STAGE_TERM_PERIOD,
    normalize_stage,
    canonical_school_name,
    next_stage,
    normalize_admission_year,
    parse_legacy_school_name,
    stage_for_date,
)
from .db import DB_PATH, connection
from .pricing import clinic_hourly_cost, clinic_settlement_amount


ATTACHMENT_ROOT = DB_PATH.parent / "uploads" / "aura-report-attachments"
ATTACHMENT_KINDS = {"blank_test", "problem_solving"}
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
LEGACY_EVENT_TZ = ZoneInfo("Asia/Seoul")


def _round_event_time(value: str | datetime) -> datetime:
    """Interpret timezone-free legacy Aura wall times in Seoul, never host local time."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    return parsed.replace(tzinfo=LEGACY_EVENT_TZ) if parsed.tzinfo is None else parsed


def _calculated_amount(hourly_rate: int, start: datetime, end: datetime | None) -> int:
    if end is None:
        return hourly_rate
    minutes = max(0, int((end - start).total_seconds() // 60))
    return round(hourly_rate * minutes / 60)


def _round_target_count(conn, round_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM aura_round_targets WHERE round_id = ?", (round_id,)
    ).fetchone()[0]


def _check_price_change(conn, user_id: int, row, start: datetime, new_amount: int,
                        approval: tuple[int, int] | list[int] | None) -> None:
    snapshot = conn.execute(
        """SELECT 1 FROM aura_settlement_snapshots
           WHERE user_id = ? AND year = ? AND month = ? LIMIT 1""",
        (user_id, start.year, start.month),
    ).fetchone()
    if (row["payment_status"] == "paid" or snapshot) and list(approval or []) != [row["amount"], new_amount]:
        raise HTTPException(status_code=409, detail={
            "code": "repricing_approval_required",
            "message": "수업 시간 변경으로 정산 금액이 달라집니다. 변경 전후 금액을 확인해주세요.",
            "changes": [{
                "roundId": row["id"], "oldAmount": row["amount"], "newAmount": new_amount,
                "delta": new_amount - row["amount"], "paid": row["payment_status"] == "paid",
                "hasSnapshot": bool(snapshot),
            }],
        })


def _validate_clinic_schedule_time(start: datetime, end: datetime):
    start, end = _round_event_time(start), _round_event_time(end)
    if end <= start:
        raise HTTPException(status_code=400, detail="종료 시각은 시작 시각보다 늦어야 합니다.")
    minutes = int((end - start).total_seconds() // 60)
    if minutes > 720:
        def label(value):
            value = value.astimezone(LEGACY_EVENT_TZ)
            return f"{value.month}월 {value.day}일 {'오전' if value.hour < 12 else '오후'} {value.hour % 12 or 12}:{value.minute:02d}"
        length = f"{minutes // 60}시간" + (f" {minutes % 60}분" if minutes % 60 else "")
        raise HTTPException(status_code=400, detail={"code":"clinic_duration_exceeded",
            "message":f"입력한 수업 시간은 {length}입니다 ({label(start)} → {label(end)}). 최대 12시간까지 저장할 수 있습니다. 종료 시각의 오전·오후를 확인해주세요."})


def _conflicting_events(
    conn, user_id: int, start: datetime, end: datetime | None, exclude_event_id: int | None = None
):
    effective_end = end or (start + timedelta(hours=1))
    rows = conn.execute(
        """SELECT e.id, e.title, e.start_time, e.end_time, st.name AS student_name
           FROM events e
           LEFT JOIN aura_sessions s ON s.event_id = e.id
           LEFT JOIN aura_students st ON st.id = s.student_id
           WHERE e.user_id = ? AND e.type = 'aura'
             AND (? IS NULL OR e.id != ?)
           ORDER BY e.start_time""",
        (user_id, exclude_event_id, exclude_event_id),
    ).fetchall()
    # Offsets and legacy Seoul wall times cannot be ordered as ISO strings.
    # Compare actual instants, while retaining the existing 12-hour clinic limit.
    start = _round_event_time(start)
    effective_end = _round_event_time(effective_end)
    overlaps = []
    for row in rows:
        try:
            existing_start = _round_event_time(row["start_time"])
            existing_end = _round_event_time(row["end_time"] or row["start_time"])
        except (ValueError, TypeError):
            continue
        if row["end_time"] is not None and existing_end - existing_start > timedelta(hours=12):
            continue
        if existing_start < effective_end and existing_end > start:
            overlaps.append(row)
    return [
        {
            "eventId": row["id"],
            "title": row["title"],
            "studentName": row["student_name"],
            "startTime": row["start_time"],
            "endTime": row["end_time"],
        }
        for row in overlaps
    ]


def _raise_conflict(conflicts):
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "schedule_conflict",
                "message": "같은 시간대에 다른 클리닉이 있습니다.",
                "conflicts": conflicts,
            },
        )


def _owned_row(conn, table: str, row_id: int, user_id: int):
    row = conn.execute(
        f"SELECT * FROM {table} WHERE id = ? AND user_id = ?", (row_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="리소스를 찾을 수 없습니다.")
    return row


def _event_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "isAllDay": bool(row["is_all_day"]),
        "status": row["status"],
        "type": row["type"],
        "groupName": row["group_name"],
        "categoryName": row["category_name"],
        "recurrenceGroupId": row["recurrence_group_id"],
        "recurrenceIndex": row["recurrence_index"],
    }


def list_events(user_id: int, start: str, end: str, event_type: str | None, status: str | None):
    query = """
        SELECT * FROM events
        WHERE user_id = ? AND start_time < ?
          AND COALESCE(end_time, start_time) >= ?
    """
    params: list[Any] = [user_id, end, start]
    if event_type:
        query += " AND type = ?"
        params.append(event_type)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY start_time"
    with connection() as conn:
        return [_event_dict(row) for row in conn.execute(query, params).fetchall()]


def create_event(user_id: int, data):
    values = data.model_dump(mode="json")
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO events
               (user_id, title, description, start_time, end_time, is_all_day,
                status, type, group_name, category_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, values["title"], values["description"], values["start_time"],
                values["end_time"], values["is_all_day"], values["status"], values["type"],
                values["group_name"], values["category_name"],
            ),
        )
        conn.commit()
        return _event_dict(_owned_row(conn, "events", cursor.lastrowid, user_id))


def create_event_series(user_id: int, data):
    values = data.model_dump(mode="json")
    repeat_count = values.pop("repeat_count")
    interval_weeks = values.pop("interval_weeks")
    values.pop("repeat_until", None)
    group_id = str(uuid4())
    first_start = data.start_time
    duration = data.end_time - first_start if data.end_time else None
    if data.repeat_until:
        starts = []
        cursor = first_start
        while cursor <= data.repeat_until and len(starts) < 365:
            starts.append(cursor)
            cursor += timedelta(weeks=interval_weeks)
        if len(starts) < 2:
            raise HTTPException(
                status_code=400,
                detail="반복 종료일은 두 번째 일정 날짜 이후여야 합니다.",
            )
    else:
        starts = [
            first_start + timedelta(weeks=index * interval_weeks)
            for index in range(repeat_count)
        ]
    ids = []
    with connection() as conn:
        for index, start in enumerate(starts):
            end = start + duration if duration else None
            cursor = conn.execute(
                """INSERT INTO events
                   (user_id, title, description, start_time, end_time, is_all_day,
                    status, type, group_name, category_name,
                    recurrence_group_id, recurrence_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    values["title"],
                    values["description"],
                    start.isoformat(),
                    end.isoformat() if end else None,
                    values["is_all_day"],
                    values["status"],
                    values["type"],
                    values["group_name"],
                    values["category_name"],
                    group_id,
                    index,
                ),
            )
            ids.append(cursor.lastrowid)
        conn.commit()
        placeholders = ", ".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT * FROM events WHERE user_id = ? AND id IN ({placeholders}) ORDER BY recurrence_index",
            (user_id, *ids),
        ).fetchall()
        return [_event_dict(row) for row in rows]


def get_event(user_id: int, event_id: int):
    with connection() as conn:
        event = _owned_row(conn, "events", event_id, user_id)
        result = _event_dict(event)
        if event["type"] == "aura":
            session = conn.execute(
                "SELECT id FROM aura_sessions WHERE event_id = ? AND user_id = ?",
                (event_id, user_id),
            ).fetchone()
            clinic_round = conn.execute(
                """SELECT id, school_id FROM aura_clinic_rounds
                   WHERE event_id = ? AND user_id = ?""",
                (event_id, user_id),
            ).fetchone()
            clinic_target = (
                conn.execute(
                    """SELECT t.id FROM aura_round_targets t
                       LEFT JOIN aura_target_reports rp ON rp.target_id = t.id
                       WHERE t.round_id = ?
                       ORDER BY CASE WHEN COALESCE(rp.status, 'draft') = 'submitted' THEN 1 ELSE 0 END,
                         t.sort_order, t.id LIMIT 1""",
                    (clinic_round["id"],),
                ).fetchone()
                if clinic_round
                else None
            )
            result["serviceLink"] = (
                f"/personal-project/aura/reports/{clinic_target['id']}"
                if clinic_target
                else f"/personal-project/aura/schools/{clinic_round['school_id']}"
                if clinic_round
                else f"/personal-project/aura/sessions/{session['id']}"
                if session
                else None
            )
        return result


def update_event(user_id: int, event_id: int, data):
    values = data.model_dump(exclude_unset=True, mode="json")
    allowed = {
        "title", "description", "start_time", "end_time", "is_all_day",
        "status", "group_name", "category_name",
    }
    values = {key: value for key, value in values.items() if key in allowed}
    with connection() as conn:
        current = _owned_row(conn, "events", event_id, user_id)
        if current["type"] != "personal":
            raise HTTPException(status_code=409, detail="서비스 일정은 해당 서비스 화면에서 수정해주세요.")
        if values:
            sets = ", ".join(f"{key} = ?" for key in values)
            conn.execute(
                f"UPDATE events SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (*values.values(), event_id, user_id),
            )
            conn.commit()
        return _event_dict(_owned_row(conn, "events", event_id, user_id))


def update_event_scope(user_id: int, event_id: int, data):
    values = data.model_dump(exclude_unset=True, mode="json")
    scope = values.pop("scope", "this")
    allowed = {
        "title", "description", "start_time", "end_time", "is_all_day",
        "status", "group_name", "category_name",
    }
    values = {key: value for key, value in values.items() if key in allowed}
    with connection() as conn:
        current = _owned_row(conn, "events", event_id, user_id)
        if current["type"] != "personal":
            raise HTTPException(
                status_code=409,
                detail="서비스 일정은 해당 서비스 화면에서 수정해주세요.",
            )
        rows = [current]
        if scope == "following" and current["recurrence_group_id"]:
            rows = conn.execute(
                """SELECT * FROM events
                   WHERE user_id = ? AND recurrence_group_id = ?
                     AND recurrence_index >= ?
                   ORDER BY recurrence_index""",
                (
                    user_id,
                    current["recurrence_group_id"],
                    current["recurrence_index"],
                ),
            ).fetchall()

        time_changed = "start_time" in values or "end_time" in values
        current_start = datetime.fromisoformat(current["start_time"])
        current_end = (
            datetime.fromisoformat(current["end_time"])
            if current["end_time"]
            else None
        )
        requested_start = (
            datetime.fromisoformat(values["start_time"])
            if "start_time" in values
            else current_start
        )
        requested_end = (
            datetime.fromisoformat(values["end_time"])
            if values.get("end_time")
            else current_end
        )
        delta = requested_start - current_start
        duration = requested_end - requested_start if requested_end else None

        for row in rows:
            row_values = dict(values)
            if time_changed:
                row_start = datetime.fromisoformat(row["start_time"]) + delta
                row_values["start_time"] = row_start.isoformat()
                row_values["end_time"] = (
                    (row_start + duration).isoformat() if duration else None
                )
            if row_values:
                sets = ", ".join(f"{key} = ?" for key in row_values)
                conn.execute(
                    f"UPDATE events SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (*row_values.values(), row["id"]),
                )
        conn.commit()
        return _event_dict(_owned_row(conn, "events", event_id, user_id))


def delete_event(user_id: int, event_id: int):
    with connection() as conn:
        event = _owned_row(conn, "events", event_id, user_id)
        if event["type"] != "personal":
            raise HTTPException(status_code=409, detail="서비스 일정은 해당 서비스 화면에서 삭제해주세요.")
        conn.execute("DELETE FROM events WHERE id = ? AND user_id = ?", (event_id, user_id))
        conn.commit()


def delete_event_scope(user_id: int, event_id: int, scope: str):
    with connection() as conn:
        event = _owned_row(conn, "events", event_id, user_id)
        if event["type"] != "personal":
            raise HTTPException(
                status_code=409,
                detail="서비스 일정은 해당 서비스 화면에서 삭제해주세요.",
            )
        if scope == "following" and event["recurrence_group_id"]:
            conn.execute(
                """DELETE FROM events
                   WHERE user_id = ? AND recurrence_group_id = ?
                     AND recurrence_index >= ?""",
                (
                    user_id,
                    event["recurrence_group_id"],
                    event["recurrence_index"],
                ),
            )
        else:
            conn.execute(
                "DELETE FROM events WHERE id = ? AND user_id = ?",
                (event_id, user_id),
            )
        conn.commit()


def list_students(user_id: int, active: bool | None, search: str | None):
    query = "SELECT * FROM aura_students WHERE user_id = ?"
    params: list[Any] = [user_id]
    if active is not None:
        query += " AND is_active = ?"
        params.append(active)
    if search:
        query += " AND (name LIKE ? OR school_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY is_active DESC, name"
    with connection() as conn:
        return [
            {
                "id": row["id"], "name": row["name"], "schoolName": row["school_name"],
                "affiliation": row["affiliation"], "memo": row["memo"],
                "isActive": bool(row["is_active"]),
            }
            for row in conn.execute(query, params).fetchall()
        ]


def create_student(user_id: int, data):
    value = data.model_dump()
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO aura_students
               (user_id, name, school_name, affiliation, memo, is_active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, value["name"], value["school_name"], value["affiliation"],
             value["memo"], value["is_active"]),
        )
        conn.commit()
        row = _owned_row(conn, "aura_students", cursor.lastrowid, user_id)
        return {"id": row["id"], "name": row["name"], "schoolName": row["school_name"],
                "affiliation": row["affiliation"], "memo": row["memo"],
                "isActive": bool(row["is_active"])}


def update_student(user_id: int, student_id: int, data):
    values = data.model_dump(exclude_unset=True)
    with connection() as conn:
        _owned_row(conn, "aura_students", student_id, user_id)
        if values:
            sets = ", ".join(f"{key} = ?" for key in values)
            conn.execute(
                f"UPDATE aura_students SET {sets} WHERE id = ? AND user_id = ?",
                (*values.values(), student_id, user_id),
            )
            conn.commit()
        row = _owned_row(conn, "aura_students", student_id, user_id)
        return {"id": row["id"], "name": row["name"], "schoolName": row["school_name"],
                "affiliation": row["affiliation"], "memo": row["memo"],
                "isActive": bool(row["is_active"])}


def _session_query() -> str:
    return """
        SELECT s.*, e.title, e.description, e.start_time, e.end_time, e.status AS event_status,
               st.name AS student_name, st.school_name, r.id AS report_id,
               r.status AS report_status, r.content_json, r.source_notes, r.submitted_at
        FROM aura_sessions s
        JOIN events e ON e.id = s.event_id
        JOIN aura_students st ON st.id = s.student_id
        LEFT JOIN aura_reports r ON r.aura_session_id = s.id
    """


def _session_dict(row):
    report_content = json.loads(row["content_json"]) if row["report_id"] is not None else None
    return {
        "id": row["id"], "eventId": row["event_id"], "studentId": row["student_id"],
        "studentName": row["student_name"], "schoolName": row["school_name_snapshot"],
        "title": row["title"], "description": row["description"],
        "startTime": row["start_time"], "endTime": row["end_time"],
        "attendanceStatus": row["attendance_status"],
        "reportRequired": bool(row["report_required"]),
        "hourlyRate": row["hourly_rate"],
        "amount": row["amount"], "paymentStatus": row["payment_status"],
        "report": None if row["report_id"] is None else {
            "id": row["report_id"], "status": row["report_status"],
            "contentJson": report_content,
            "analysisJson": _analysis_document(report_content),
            "sourceNotes": row["source_notes"],
            "submittedAt": row["submitted_at"],
        },
    }


def create_session(user_id: int, data):
    value = data.model_dump(mode="json")
    with connection() as conn:
        student = _owned_row(conn, "aura_students", value["student_id"], user_id)
        if not data.allow_overlap:
            _raise_conflict(
                _conflicting_events(conn, user_id, data.start_time, data.end_time)
            )
        amount = _calculated_amount(data.hourly_rate, data.start_time, data.end_time)
        try:
            event = conn.execute(
                """INSERT INTO events
                   (user_id, title, description, start_time, end_time, status, type, category_name)
                   VALUES (?, ?, ?, ?, ?, 'todo', 'aura', '클리닉')""",
                (
                    user_id, value["title"] or f"{student['name']} 클리닉",
                    value["description"], value["start_time"], value["end_time"],
                ),
            )
            session = conn.execute(
                """INSERT INTO aura_sessions
                   (user_id, event_id, student_id, session_number, report_required,
                    hourly_rate, amount, school_name_snapshot)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, event.lastrowid, value["student_id"], 0,
                    value["report_required"], value["hourly_rate"], amount,
                    student["school_name"],
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        row = conn.execute(
            _session_query() + " WHERE s.id = ? AND s.user_id = ?",
            (session.lastrowid, user_id),
        ).fetchone()
        return _session_dict(row)


def create_session_series(user_id: int, data):
    first_start = data.first_start_time
    duration = timedelta(minutes=data.duration_minutes)
    interval = timedelta(weeks=data.interval_weeks)
    created_ids: list[int] = []
    with connection() as conn:
        student = _owned_row(conn, "aura_students", data.student_id, user_id)
        conflicts = []
        for index in range(data.repeat_count):
            start = first_start + interval * index
            conflicts.extend(
                _conflicting_events(conn, user_id, start, start + duration)
            )
        if conflicts and not data.allow_overlap:
            _raise_conflict(conflicts)
        try:
            for index in range(data.repeat_count):
                start = first_start + interval * index
                end = start + duration
                event = conn.execute(
                    """INSERT INTO events
                       (user_id, title, description, start_time, end_time, status, type, category_name)
                       VALUES (?, ?, ?, ?, ?, 'todo', 'aura', '클리닉')""",
                    (
                        user_id, f"{student['name']} 클리닉", data.description,
                        start.isoformat(), end.isoformat(),
                    ),
                )
                session = conn.execute(
                    """INSERT INTO aura_sessions
                       (user_id, event_id, student_id, session_number, report_required,
                        hourly_rate, amount, school_name_snapshot)
                       VALUES (?, ?, ?, 0, ?, ?, ?, ?)""",
                    (
                        user_id, event.lastrowid, data.student_id, data.report_required,
                        data.hourly_rate,
                        _calculated_amount(data.hourly_rate, start, end),
                        student["school_name"],
                    ),
                )
                created_ids.append(session.lastrowid)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        rows = [
            conn.execute(
                _session_query() + " WHERE s.id = ? AND s.user_id = ?",
                (session_id, user_id),
            ).fetchone()
            for session_id in created_ids
        ]
        return [_session_dict(row) for row in rows]


def list_sessions(user_id: int, start: str | None, end: str | None, student_id: int | None):
    query = _session_query() + " WHERE s.user_id = ?"
    params: list[Any] = [user_id]
    if start:
        query += " AND e.start_time >= ?"
        params.append(start)
    if end:
        query += " AND e.start_time < ?"
        params.append(end)
    if student_id:
        query += " AND s.student_id = ?"
        params.append(student_id)
    query += " ORDER BY e.start_time DESC"
    with connection() as conn:
        return [_session_dict(row) for row in conn.execute(query, params).fetchall()]


def get_session(user_id: int, session_id: int):
    with connection() as conn:
        row = conn.execute(
            _session_query() + " WHERE s.id = ? AND s.user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="클리닉을 찾을 수 없습니다.")
        return _session_dict(row)


def update_session(user_id: int, session_id: int, data):
    values = data.model_dump(exclude_unset=True, mode="json")
    allow_overlap = values.pop("allow_overlap", False)
    event_values = {k: values.pop(k) for k in ("start_time", "end_time") if k in values}
    with connection() as conn:
        session = _owned_row(conn, "aura_sessions", session_id, user_id)
        event = _owned_row(conn, "events", session["event_id"], user_id)
        start = data.start_time or datetime.fromisoformat(event["start_time"].replace("Z", "+00:00"))
        end = (
            data.end_time
            if "end_time" in event_values
            else datetime.fromisoformat(event["end_time"].replace("Z", "+00:00"))
            if event["end_time"]
            else None
        )
        if end and end < start:
            raise HTTPException(status_code=400, detail="종료 시간은 시작 시간보다 빠를 수 없습니다.")
        if end and end - start > timedelta(hours=12):
            raise HTTPException(status_code=400, detail="클리닉 일정은 12시간을 넘을 수 없습니다.")
        if event_values and not allow_overlap:
            _raise_conflict(
                _conflicting_events(conn, user_id, start, end, session["event_id"])
            )
        hourly_rate = data.hourly_rate if data.hourly_rate is not None else session["hourly_rate"]
        if event_values or data.hourly_rate is not None:
            values["amount"] = _calculated_amount(hourly_rate, start, end)
        if values:
            sets = ", ".join(f"{key} = ?" for key in values)
            conn.execute(
                f"UPDATE aura_sessions SET {sets} WHERE id = ? AND user_id = ?",
                (*values.values(), session_id, user_id),
            )
        if event_values:
            sets = ", ".join(f"{key} = ?" for key in event_values)
            conn.execute(
                f"UPDATE events SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (*event_values.values(), session["event_id"], user_id),
            )
        conn.commit()
    return get_session(user_id, session_id)


def delete_session(user_id: int, session_id: int):
    with connection() as conn:
        session = _owned_row(conn, "aura_sessions", session_id, user_id)
        conn.execute(
            "DELETE FROM events WHERE id = ? AND user_id = ?",
            (session["event_id"], user_id),
        )
        conn.commit()


def create_report(user_id: int, session_id: int, data):
    with connection() as conn:
        session = _owned_row(conn, "aura_sessions", session_id, user_id)
        try:
            cursor = conn.execute(
                """INSERT INTO aura_reports (aura_session_id, content_json, source_notes)
                   VALUES (?, ?, ?)""",
                (session_id, json.dumps(data.content_json, ensure_ascii=False), data.source_notes),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=409, detail="이미 리포트가 존재합니다.") from exc
        return {"id": cursor.lastrowid}


def update_report(user_id: int, report_id: int, data, submit: bool = False):
    values = data.model_dump(exclude_unset=True) if data else {}
    if "content_json" in values:
        values["content_json"] = json.dumps(values["content_json"], ensure_ascii=False)
    if submit:
        values["status"] = "submitted"
        values["submitted_at"] = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        row = conn.execute(
            """SELECT r.* FROM aura_reports r
               JOIN aura_sessions s ON s.id = r.aura_session_id
               WHERE r.id = ? AND s.user_id = ?""",
            (report_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
        if values:
            sets = ", ".join(f"{key} = ?" for key in values)
            conn.execute(
                f"UPDATE aura_reports SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (*values.values(), report_id),
            )
            conn.commit()
        return get_session(user_id, row["aura_session_id"])["report"]


def _analysis_document(content: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, stable representation for a later GPT prompt."""
    segments: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []

    def visit(block: dict[str, Any]):
        block_id = str(block.get("id", ""))
        block_type = str(block.get("type", "paragraph"))
        offset = 0
        for chunk in block.get("children", []):
            if not isinstance(chunk, dict):
                continue
            text = str(chunk.get("text", ""))
            end = offset + len(text)
            formats = [
                {"name": key, "value": value}
                for key, value in chunk.items()
                if key not in {"type", "text"}
                and value is not None
                and value is not False
                and value != ""
            ]
            segments.append({
                "blockId": block_id, "blockType": block_type,
                "start": offset, "end": end, "text": text, "formats": formats,
            })
            highlight = chunk.get("highlightColor")
            if highlight:
                annotations.append({
                    "type": "highlight", "blockId": block_id, "start": offset,
                    "end": end, "color": highlight, "text": text,
                })
            offset = end

    for block in content.get("blocks", []):
        if not isinstance(block, dict):
            continue
        if block.get("type") == "table":
            for row in block.get("rows", []):
                for cell in row:
                    for child in cell.get("blocks", []):
                        visit(child)
        else:
            visit(block)
    return {
        "version": 1,
        "documentId": content.get("documentId"),
        "segments": segments,
        "annotations": annotations,
    }


def settlements(user_id: int, year: int, month: int):
    start = f"{year:04d}-{month:02d}-01"
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = f"{next_year:04d}-{next_month:02d}-01"
    rows = list_sessions(user_id, start, end, None)
    items = [
        row for row in rows
        if row["attendanceStatus"] == "completed"
    ]
    return {
        "year": year, "month": month, "totalAmount": sum(row["amount"] for row in items),
        "completedCount": len(items), "items": items,
    }


# School-first Aura workflow -------------------------------------------------


def _school_dict(row, round_count: int = 0):
    admission_year, school_name = parse_legacy_school_name(row["name"])
    admission_year = row["admission_year"] or admission_year
    return {
        "id": row["id"],
        "name": row["name"],
        "admissionYear": admission_year,
        "schoolName": school_name,
        "memo": row["memo"],
        "isActive": bool(row["is_active"]),
        "roundCount": round_count,
        "priority": row["priority"],
        "termStatus": row["term_status"],
        "currentStage": normalize_stage(row["current_stage"]),
        "recommendedStage": stage_for_date(admission_year, datetime.now().date()),
        "freeForThreePlus": bool(row["free_for_three_plus"]),
    }


def list_schools(user_id: int):
    with connection() as conn:
        rows = conn.execute(
            """SELECT s.*, COUNT(r.id) AS round_count
               FROM aura_schools s
               LEFT JOIN aura_clinic_rounds r ON r.school_id = s.id
               WHERE s.user_id = ?
               GROUP BY s.id
               ORDER BY (s.term_status = 'active') DESC,
                        s.priority DESC, s.admission_year DESC, s.is_active DESC, s.name""",
            (user_id,),
        ).fetchall()
        return [_school_dict(row, row["round_count"]) for row in rows]


def create_school(user_id: int, data):
    value = data.model_dump()
    admission_year = normalize_admission_year(value.pop("admission_year"))
    school_name = value.pop("school_name").strip()
    current_stage = value.pop("current_stage") or stage_for_date(
        admission_year, datetime.now().date()
    )
    name = canonical_school_name(admission_year, school_name)
    with connection() as conn:
        max_priority = conn.execute(
            "SELECT COALESCE(MAX(priority), 0) FROM aura_schools WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if value["priority"] == 0:
            value["priority"] = max_priority + 1
        try:
            cursor = conn.execute(
                """INSERT INTO aura_schools
                   (user_id, name, memo, priority,
                    term_period, free_for_three_plus, admission_year, current_stage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    name,
                    value["memo"],
                    value["priority"],
                    STAGE_TERM_PERIOD[current_stage],
                    value["free_for_three_plus"],
                    admission_year,
                    current_stage,
                ),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="같은 입학연도와 학교가 이미 등록되어 있습니다.",
            ) from exc
        return _school_dict(
            _owned_row(conn, "aura_schools", cursor.lastrowid, user_id)
        )


def update_school(user_id: int, school_id: int, data):
    values = data.model_dump(exclude_unset=True)
    if "current_stage" in values:
        values["term_period"] = STAGE_TERM_PERIOD[values["current_stage"]]
    with connection() as conn:
        _owned_row(conn, "aura_schools", school_id, user_id)
        if values:
            sets = ", ".join(f"{key} = ?" for key in values)
            try:
                conn.execute(
                    f"UPDATE aura_schools SET {sets} WHERE id = ? AND user_id = ?",
                    (*values.values(), school_id, user_id),
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise HTTPException(
                    status_code=409, detail="학교 설정을 변경하지 못했습니다."
                ) from exc
        return _school_dict(_owned_row(conn, "aura_schools", school_id, user_id))


def advance_school_stages(user_id: int):
    with connection() as conn:
        schools = conn.execute(
            """SELECT * FROM aura_schools
               WHERE user_id = ? AND is_active = 1 AND term_status = 'active'""",
            (user_id,),
        ).fetchall()
        for school in schools:
            stage = next_stage(school["current_stage"])
            conn.execute(
                """UPDATE aura_schools SET current_stage = ?, term_period = ?
                   WHERE id = ?""",
                (stage, STAGE_TERM_PERIOD[stage], school["id"]),
            )
        conn.commit()
    return list_schools(user_id)


def move_school(user_id: int, school_id: int, direction: str):
    if direction not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="이동 방향을 확인해주세요.")
    with connection() as conn:
        current = _owned_row(conn, "aura_schools", school_id, user_id)
        schools = conn.execute(
            """SELECT * FROM aura_schools
               WHERE user_id = ? AND term_status = ? AND current_stage = ?
               ORDER BY priority DESC, name""",
            (user_id, current["term_status"], current["current_stage"]),
        ).fetchall()
        for index, school in enumerate(schools):
            conn.execute(
                "UPDATE aura_schools SET priority = ? WHERE id = ?",
                (len(schools) - index, school["id"]),
            )
        current_index = next(
            index for index, school in enumerate(schools) if school["id"] == school_id
        )
        neighbor_index = current_index + (-1 if direction == "up" else 1)
        if neighbor_index < 0 or neighbor_index >= len(schools):
            conn.commit()
            return _school_dict(current)
        neighbor = schools[neighbor_index]
        current_priority = len(schools) - current_index
        neighbor_priority = len(schools) - neighbor_index
        conn.execute(
            "UPDATE aura_schools SET priority = ? WHERE id = ?",
            (neighbor_priority, current["id"]),
        )
        conn.execute(
            "UPDATE aura_schools SET priority = ? WHERE id = ?",
            (current_priority, neighbor["id"]),
        )
        conn.commit()
        return _school_dict(
            _owned_row(conn, "aura_schools", school_id, user_id)
        )


def reorder_schools(user_id: int, school_ids: list[int]):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT id FROM aura_schools WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
        owned_ids = {int(row["id"]) for row in rows}
        requested_ids = [int(value) for value in school_ids]
        if len(requested_ids) != len(set(requested_ids)) or set(requested_ids) != owned_ids:
            raise HTTPException(status_code=400, detail="학교 순서가 최신 목록과 다릅니다. 다시 불러와주세요.")
        count = len(requested_ids)
        for index, school_id in enumerate(requested_ids):
            conn.execute(
                "UPDATE aura_schools SET priority = ? WHERE id = ? AND user_id = ?",
                (count - index, school_id, user_id),
            )
        conn.commit()
    return list_schools(user_id)


def delete_school(user_id: int, school_id: int):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _owned_row(conn, "aura_schools", school_id, user_id)
        attachment_files = _journal_parent_files(conn, user_id, "school", school_id=school_id)
        event_rows = conn.execute(
            """SELECT event_id FROM aura_clinic_rounds
               WHERE user_id = ? AND school_id = ?""",
            (user_id, school_id),
        ).fetchall()
        for row in event_rows:
            conn.execute(
                "DELETE FROM events WHERE id = ? AND user_id = ?",
                (row["event_id"], user_id),
            )
        conn.execute(
            "DELETE FROM aura_round_templates WHERE user_id = ? AND school_id = ?",
            (user_id, school_id),
        )
        conn.execute(
            "DELETE FROM aura_schools WHERE id = ? AND user_id = ?",
            (school_id, user_id),
        )
        conn.commit()
    _remove_attachment_files(attachment_files)


def _target_dict(row):
    return {
        "id": row["id"],
        "studentName": row["student_name"],
        "report": None
        if row["report_id"] is None
        else {
            "id": row["report_id"],
            "status": row["report_status"],
            "templateVersion": row["template_version"],
            "submittedAt": row["submitted_at"],
        },
    }


def _round_dict(conn, row):
    round_numbers = json.loads(row["round_numbers_json"] or "[]")
    if not round_numbers:
        round_numbers = [row["round_number"]]
    targets = conn.execute(
        """SELECT t.*, rp.id AS report_id, rp.status AS report_status,
                  rp.template_version, rp.submitted_at
           FROM aura_round_targets t
           LEFT JOIN aura_target_reports rp ON rp.target_id = t.id
           WHERE t.round_id = ?
           ORDER BY t.sort_order, t.id""",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "schoolId": row["school_id"],
        "schoolName": row["school_name"],
        "progressStage": row["progress_stage"],
        "parentFreeForThreePlus": bool(row["school_free_for_three_plus"]),
        "eventId": row["event_id"],
        "roundNumber": row["round_number"],
        "roundNumbers": round_numbers,
        "roundLabel": f"{','.join(str(number) for number in round_numbers)}회차",
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "description": row["description"],
        "modality": row["modality"],
        "attendanceStatus": row["attendance_status"],
        "reportRequired": bool(row["report_required"]),
        "hourlyRate": row["hourly_rate"],
        "amount": row["amount"],
        "paymentStatus": row["payment_status"],
        "seriesGroupId": row["series_group_id"],
        "seriesIndex": row["series_index"],
        "targets": [_target_dict(target) for target in targets],
    }


def _round_query():
    return """
        SELECT r.*, s.name AS school_name,
               s.free_for_three_plus AS school_free_for_three_plus,
               e.start_time, e.end_time,
               e.description, e.title
        FROM aura_clinic_rounds r
        JOIN aura_schools s ON s.id = r.school_id
        JOIN events e ON e.id = r.event_id
    """


def _assert_round_numbers_available(
    conn,
    school_id: int,
    round_numbers: list[int],
    exclude_ids: set[int] | None = None,
):
    requested = set(round_numbers)
    excluded = exclude_ids or set()
    rows = conn.execute(
        """SELECT id, round_number, round_numbers_json
           FROM aura_clinic_rounds WHERE school_id = ?""",
        (school_id,),
    ).fetchall()
    for row in rows:
        if row["id"] in excluded:
            continue
        existing = set(json.loads(row["round_numbers_json"] or "[]"))
        if not existing:
            existing = {row["round_number"]}
        overlap = requested & existing
        if overlap:
            labels = ",".join(str(number) for number in sorted(overlap))
            raise HTTPException(
                status_code=409,
                detail=f"이미 등록된 회차가 있습니다: {labels}회차",
            )


def list_clinic_rounds(
    user_id: int,
    school_id: int | None = None,
    start: str | None = None,
    end: str | None = None,
):
    query = _round_query() + " WHERE r.user_id = ?"
    params: list[Any] = [user_id]
    if school_id:
        query += " AND r.school_id = ?"
        params.append(school_id)
    if start:
        query += " AND e.start_time >= ?"
        params.append(start)
    if end:
        query += " AND e.start_time < ?"
        params.append(end)
    query += " ORDER BY s.name, r.round_number, e.start_time"
    with connection() as conn:
        return [
            _round_dict(conn, row) for row in conn.execute(query, params).fetchall()
        ]


def get_school(user_id: int, school_id: int):
    with connection() as conn:
        school = _owned_row(conn, "aura_schools", school_id, user_id)
        result = _school_dict(school)
        rows = conn.execute(
            _round_query()
            + " WHERE r.user_id = ? AND r.school_id = ? ORDER BY r.round_number",
            (user_id, school_id),
        ).fetchall()
        result["rounds"] = [_round_dict(conn, row) for row in rows]
        return result


def export_school_archive(user_id: int, school_id: int):
    school = get_school(user_id, school_id)
    with connection() as conn:
        templates = conn.execute(
            """SELECT progress_stage, round_number, version, content_json, is_active, created_at
               FROM aura_round_templates
               WHERE user_id = ? AND school_id = ?
               ORDER BY round_number, version""",
            (user_id, school_id),
        ).fetchall()
        reports = conn.execute(
            """SELECT t.student_name, r.progress_stage, r.round_numbers_json, rp.template_version,
                      rp.content_json, rp.source_notes, rp.question_checks_json, rp.status,
                      rp.submitted_at, rp.updated_at
               FROM aura_target_reports rp
               JOIN aura_round_targets t ON t.id = rp.target_id
               JOIN aura_clinic_rounds r ON r.id = t.round_id
               JOIN events e ON e.id = r.event_id
               WHERE r.user_id = ? AND r.school_id = ?
               ORDER BY e.start_time, t.sort_order""",
            (user_id, school_id),
        ).fetchall()
        return {
            "exportedAt": datetime.now(timezone.utc).isoformat(),
            "school": school,
            "templates": [
                {
                    "progressStage": row["progress_stage"],
                    "roundNumber": row["round_number"],
                    "version": row["version"],
                    "contentJson": json.loads(row["content_json"]),
                    "isActive": bool(row["is_active"]),
                    "createdAt": row["created_at"],
                }
                for row in templates
            ],
            "reports": [
                {
                    "studentName": row["student_name"],
                    "progressStage": row["progress_stage"],
                    "roundNumbers": json.loads(row["round_numbers_json"] or "[]"),
                    "templateVersion": row["template_version"],
                    "contentJson": json.loads(row["content_json"]),
                    "sourceNotes": row["source_notes"],
                    "questionChecks": json.loads(row["question_checks_json"] or "{}"),
                    "status": row["status"],
                    "submittedAt": row["submitted_at"],
                    "updatedAt": row["updated_at"],
                }
                for row in reports
            ],
        }


def create_clinic_round(user_id: int, data):
    with connection() as conn:
        school = _owned_row(conn, "aura_schools", data.school_id, user_id)
        if not data.allow_overlap:
            _raise_conflict(
                _conflicting_events(
                    conn, user_id, data.start_time, data.end_time
                )
            )
        progress_stage = data.progress_stage or normalize_stage(school["current_stage"])
        # New schedules are uncalculated until the owner requests settlement calculation.
        hourly_rate = 0
        amount = 0
        try:
            event = conn.execute(
                """INSERT INTO events
                   (user_id, title, description, start_time, end_time, status,
                    type, category_name)
                   VALUES (?, ?, ?, ?, ?, 'todo', 'aura', '클리닉')""",
                (
                    user_id,
                    f"{school['name']} {data.round_number}회차 클리닉",
                    data.description,
                    data.start_time.isoformat(),
                    data.end_time.isoformat(),
                ),
            )
            round_cursor = conn.execute(
                """INSERT INTO aura_clinic_rounds
                   (user_id, school_id, event_id, round_number, report_required,
                    hourly_rate, amount, round_numbers_json, progress_stage, modality)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    data.school_id,
                    event.lastrowid,
                    data.round_number,
                    data.report_required,
                    hourly_rate,
                    amount,
                    json.dumps([data.round_number]),
                    progress_stage,
                    data.modality,
                ),
            )
            for index, name in enumerate(data.student_names):
                conn.execute(
                    """INSERT INTO aura_round_targets
                       (round_id, student_name, sort_order)
                       VALUES (?, ?, ?)""",
                    (round_cursor.lastrowid, name, index),
                )
            # Keep prior generated settlement until separately confirmed regeneration.
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="이 학교에 같은 회차가 이미 존재합니다.",
            ) from exc
        row = conn.execute(
            _round_query() + " WHERE r.id = ? AND r.user_id = ?",
            (round_cursor.lastrowid, user_id),
        ).fetchone()
        return _round_dict(conn, row)


def create_clinic_round_series(user_id: int, data):
    with connection() as conn:
        school = _owned_row(conn, "aura_schools", data.school_id, user_id)
        duration = data.end_time - data.start_time
        starts = [
            data.start_time + timedelta(weeks=index * data.interval_weeks)
            for index in range(data.repeat_count)
        ]
        if not data.allow_overlap:
            for start in starts:
                _raise_conflict(
                    _conflicting_events(conn, user_id, start, start + duration)
                )

        progress_stage = data.progress_stage or normalize_stage(school["current_stage"])
        # New schedules are uncalculated until the owner requests settlement calculation.
        hourly_rate = 0
        amount = 0
        round_ids = []
        group_id = str(uuid4())
        occurrences = data.round_numbers_by_occurrence or [
            [number]
            for number in (
                data.round_numbers
                or [data.round_number + index for index in range(data.repeat_count)]
            )
        ]
        try:
            for index, start in enumerate(starts):
                end = start + duration
                round_numbers = occurrences[index]
                round_label = ",".join(str(number) for number in round_numbers)
                event = conn.execute(
                    """INSERT INTO events
                       (user_id, title, description, start_time, end_time, status,
                        type, category_name)
                       VALUES (?, ?, ?, ?, ?, 'todo', 'aura', '클리닉')""",
                    (
                        user_id,
                        f"{school['name']} {round_label}회차 클리닉",
                        data.description,
                        start.isoformat(),
                        end.isoformat(),
                    ),
                )
                round_cursor = conn.execute(
                    """INSERT INTO aura_clinic_rounds
                       (user_id, school_id, event_id, round_number,
                        round_numbers_json, report_required, hourly_rate, amount,
                        series_group_id, series_index, progress_stage, modality)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        data.school_id,
                        event.lastrowid,
                        round_numbers[0],
                        json.dumps(round_numbers),
                        data.report_required,
                        hourly_rate,
                        amount,
                        group_id,
                        index,
                        progress_stage,
                        data.modality,
                    ),
                )
                round_ids.append(round_cursor.lastrowid)
                for target_index, name in enumerate(data.student_names):
                    conn.execute(
                        """INSERT INTO aura_round_targets
                           (round_id, student_name, sort_order)
                           VALUES (?, ?, ?)""",
                        (round_cursor.lastrowid, name, target_index),
                    )
            # New rounds do not erase historical monthly snapshots.
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="반복 범위 안에 이미 존재하는 학교·회차가 있습니다.",
            ) from exc

        placeholders = ", ".join("?" for _ in round_ids)
        rows = conn.execute(
            _round_query()
            + f" WHERE r.user_id = ? AND r.id IN ({placeholders})"
            + " ORDER BY r.series_index, r.id",
            (user_id, *round_ids),
        ).fetchall()
        return [_round_dict(conn, row) for row in rows]


def get_clinic_round(user_id: int, round_id: int):
    with connection() as conn:
        row = conn.execute(
            _round_query() + " WHERE r.id = ? AND r.user_id = ?",
            (round_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="회차를 찾을 수 없습니다.")
        return _round_dict(conn, row)


def _round_scope_rows(conn, user_id: int, current, scope: str, *, same_school: bool = False):
    if scope in ("following", "all") and current["series_group_id"]:
        school_filter = "AND school_id = ?" if same_school else ""
        params = (user_id, current["series_group_id"], current["school_id"], (current["series_index"] if scope == "following" else -1)) if same_school else (user_id, current["series_group_id"], (current["series_index"] if scope == "following" else -1))
        return conn.execute(
            f"""SELECT * FROM aura_clinic_rounds
               WHERE user_id = ? AND series_group_id = ? {school_filter}
                 AND series_index >= ? ORDER BY series_index, id""",
            params,
        ).fetchall()
    return [current]


def preview_clinic_round_modality(user_id: int, round_id: int, scope: str):
    with connection() as conn:
        # Keep the selected IDs and their content on one SQLite read snapshot.
        conn.execute("BEGIN")
        current = _owned_row(conn, "aura_clinic_rounds", round_id, user_id)
        rows = _round_scope_rows(conn, user_id, current, scope, same_school=False)
        rounds = _modality_preview_rounds(conn, user_id, rows)
        return {"scope": scope, "rounds": rounds, "roundState": _modality_round_state(rounds)}


def _modality_preview_rounds(conn, user_id: int, rows):
    return [_round_dict(conn, conn.execute(
        _round_query() + " WHERE r.id = ? AND r.user_id = ?",
        (row["id"], user_id),
    ).fetchone()) for row in rows]


def _modality_round_state(rounds: list[dict]) -> str:
    """Content snapshot of previewed rounds, excluding unrelated target report edits."""
    snapshot = [{**{k: v for k, v in row.items() if k != "targets"},
                 "targets": [{"id": target["id"], "studentName": target["studentName"]}
                             for target in row["targets"]]} for row in rounds]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _update_round_targets(conn, round_id: int, targets: list[dict], *, confirm_removal: bool, confirm_rename: bool):
    existing = conn.execute(
        "SELECT id, student_name FROM aura_round_targets WHERE round_id = ?", (round_id,)
    ).fetchall()
    by_id = {row['id']: row for row in existing}
    retained = [entry['id'] for entry in targets if entry['id'] is not None]
    if len(retained) != len(set(retained)) or any(target_id not in by_id for target_id in retained):
        raise HTTPException(status_code=409, detail="학생 ID가 이 회차에 속하지 않거나 중복됩니다.")
    removed = set(by_id) - set(retained)
    if removed and not confirm_removal:
        raise HTTPException(status_code=409, detail="학생 제거에는 명시적 확인이 필요합니다.")
    if removed:
        placeholders = ', '.join('?' for _ in removed)
        protected = conn.execute(
            f"SELECT target_id FROM aura_target_reports WHERE target_id IN ({placeholders}) LIMIT 1",
            tuple(removed),
        ).fetchone()
        if protected:
            raise HTTPException(status_code=409, detail="리포트가 있는 학생은 제거할 수 없습니다.")
    renamed = [entry for entry in targets if entry['id'] is not None
               and by_id[entry['id']]['student_name'] != entry['student_name']]
    if renamed and not confirm_rename:
        raise HTTPException(status_code=409, detail="학생 ID에 연결된 이름 변경에는 동일인 확인이 필요합니다.")
    # Validate all identities and conflicts before the first mutation.
    for target_id in removed:
        conn.execute("DELETE FROM aura_round_targets WHERE id = ?", (target_id,))
    for index, entry in enumerate(targets):
        if entry['id'] is None:
            conn.execute(
                "INSERT INTO aura_round_targets (round_id, student_name, sort_order) VALUES (?, ?, ?)",
                (round_id, entry['student_name'], index),
            )
        else:
            conn.execute(
                "UPDATE aura_round_targets SET student_name = ?, sort_order = ? WHERE id = ? AND round_id = ?",
                (entry['student_name'], index, entry['id'], round_id),
            )


def update_clinic_round(user_id: int, round_id: int, data):
    values = data.model_dump(exclude_unset=True, mode="json")
    allow_overlap = values.pop("allow_overlap", False)
    scope = values.pop("scope", "this")
    expected_round_ids = values.pop("expected_round_ids", None)
    expected_round_state = values.pop("expected_round_state", None)
    student_names = values.pop("student_names", None)
    target_edits = values.pop("targets", None)
    if target_edits is not None:
        target_edits = [dict(id=None, **entry) if 'id' not in entry else entry for entry in target_edits]
    confirm_removal = values.pop("confirm_target_removal", False)
    confirm_rename = values.pop("confirm_identity_rename", False)
    approved_price_changes = values.pop("approved_price_changes", {})
    if student_names is not None:
        raise HTTPException(status_code=409, detail="학생 목록 편집에는 학생 ID가 필요합니다. targets를 사용해주세요.")
    if target_edits is not None and scope != "this":
        raise HTTPException(status_code=409, detail="학생 목록은 한 회차씩 ID로 편집해주세요.")
    requested_school_id = values.get("school_id")
    requested_round_number = values.pop("round_number", None)
    requested_round_numbers = values.pop("round_numbers", None)
    if requested_round_numbers:
        requested_round_number = requested_round_numbers[0]
    event_values = {
        key: values.pop(key)
        for key in ("start_time", "end_time", "description")
        if key in values
    }
    time_changed = "start_time" in event_values or "end_time" in event_values
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = _owned_row(conn, "aura_clinic_rounds", round_id, user_id)
        requested_school = (
            _owned_row(conn, "aura_schools", requested_school_id, user_id)
            if requested_school_id is not None
            else _owned_row(conn, "aura_schools", current["school_id"], user_id)
        )
        # A school-only PATCH moves the round, not its historical exam stage.
        # Creation may default to the school's current stage; edits never do.
        event = _owned_row(conn, "events", current["event_id"], user_id)
        original_start = _round_event_time(event["start_time"])
        original_end = _round_event_time(event["end_time"])
        start = _round_event_time(data.start_time) if "start_time" in event_values else original_start
        end = (
            _round_event_time(data.end_time)
            if "end_time" in event_values
            else original_end
        )
        _validate_clinic_schedule_time(start, end)
        rounds = _round_scope_rows(conn, user_id, current, scope, same_school=False)
        if "modality" in values and scope != "this":
            actual_ids = [item["id"] for item in rounds]
            if (expected_round_ids != actual_ids or not expected_round_state
                    or expected_round_state != _modality_round_state(
                        _modality_preview_rounds(conn, user_id, rounds))):
                raise HTTPException(status_code=409, detail={
                    "message": "변경 대상 회차의 내용이 미리보기와 다릅니다. 다시 확인해주세요.",
                    "affectedRoundIds": actual_ids,
                })
        round_delta = (
            requested_round_number - current["round_number"]
            if requested_round_number is not None
            else 0
        )
        if requested_school_id is not None or requested_round_number is not None:
            all_target_numbers = []
            for item in rounds:
                existing_numbers = json.loads(item["round_numbers_json"] or "[]") or [
                    item["round_number"]
                ]
                all_target_numbers.extend(
                    requested_round_numbers
                    if requested_round_numbers is not None
                    and item["id"] == current["id"]
                    else [number + round_delta for number in existing_numbers]
                )
            if len(all_target_numbers) != len(set(all_target_numbers)):
                raise HTTPException(
                    status_code=409,
                    detail="변경 범위 안에서 같은 회차가 중복됩니다.",
                )
        start_delta = start - original_start
        end_delta = end - original_end
        affected_starts = []
        for item in rounds:
            item_event = _owned_row(conn, "events", item["event_id"], user_id)
            item_start = _round_event_time(item_event["start_time"])
            target_start = item_start
            existing_numbers = json.loads(item["round_numbers_json"] or "[]") or [
                item["round_number"]
            ]
            target_numbers = (
                requested_round_numbers
                if requested_round_numbers is not None and item["id"] == current["id"]
                else [number + round_delta for number in existing_numbers]
                if requested_round_number is not None
                else existing_numbers
            )
            if values or requested_round_number is not None:
                item_values = dict(values)
                if requested_round_number is not None:
                    item_values["round_number"] = target_numbers[0]
                    item_values["round_numbers_json"] = json.dumps(target_numbers)
                if item_values:
                    sets = ", ".join(f"{key} = ?" for key in item_values)
                    conn.execute(
                        f"UPDATE aura_clinic_rounds SET {sets} WHERE id = ? AND user_id = ?",
                        (*item_values.values(), item["id"], user_id),
                    )
            if event_values:
                item_event = _owned_row(conn, "events", item["event_id"], user_id)
                item_event_values = {
                    key: value
                    for key, value in event_values.items()
                    if key not in ("start_time", "end_time")
                }
                if time_changed:
                    item_start = _round_event_time(item_event["start_time"])
                    target_start = item_start + start_delta
                    target_end = _round_event_time(item_event["end_time"]) + end_delta
                    _validate_clinic_schedule_time(target_start, target_end)
                    item_event_values["start_time"] = target_start.isoformat()
                    item_event_values["end_time"] = target_end.isoformat()
                sets = ", ".join(f"{key} = ?" for key in item_event_values)
                conn.execute(
                    f"""UPDATE events SET {sets},
                        updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (*item_event_values.values(), item["event_id"]),
                )
            affected_starts.append(item_start)
            affected_starts.append(target_start if time_changed else item_start)
            if requested_school_id is not None or requested_round_number is not None:
                target_round_label = ",".join(str(number) for number in target_numbers)
                conn.execute(
                    "UPDATE events SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        f"{requested_school['name']} {target_round_label}회차 클리닉",
                        item["event_id"],
                    ),
                )
            if target_edits is not None:
                _update_round_targets(
                    conn, item['id'], target_edits,
                    confirm_removal=confirm_removal, confirm_rename=confirm_rename,
                )
            if target_numbers != existing_numbers or (
                "progress_stage" in values
                and values["progress_stage"] != item["progress_stage"]
            ):
                conn.execute(
                    """DELETE FROM aura_target_reports
                       WHERE has_user_edits = 0 AND status = 'draft'
                         AND generated_report_json IS NULL
                         AND NOT EXISTS (
                           SELECT 1 FROM aura_report_attachments a
                           WHERE a.target_report_id = aura_target_reports.id
                         )
                         AND target_id IN (
                           SELECT id FROM aura_round_targets WHERE round_id = ?
                         )""",
                    (item["id"],),
                )
        # Existing monthly settlements are immutable historical snapshots.
        # Explicit regeneration has a separate compare-and-confirm boundary.
        conn.commit()
    result = get_clinic_round(user_id, round_id)
    result["affectedRoundIds"] = [item["id"] for item in rounds]
    return result


def delete_clinic_round(user_id: int, round_id: int, scope: str = "this"):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = _owned_row(conn, "aura_clinic_rounds", round_id, user_id)
        rounds = _round_scope_rows(conn, user_id, current, scope)
        attachment_files = []
        for item in rounds:
            attachment_files.extend(_journal_parent_files(conn, user_id, "round", round_id=item["id"]))
            _owned_row(conn, "events", item["event_id"], user_id)
            conn.execute("DELETE FROM events WHERE id = ? AND user_id = ?", (item["event_id"], user_id))
        conn.commit()
    _remove_attachment_files(attachment_files)


def add_round_target(user_id: int, round_id: int, data):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        round_row = _owned_row(conn, "aura_clinic_rounds", round_id, user_id)
        event = _owned_row(conn, "events", round_row["event_id"], user_id)
        start = datetime.fromisoformat(event["start_time"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(event["end_time"].replace("Z", "+00:00"))
        order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM aura_round_targets WHERE round_id = ?",
            (round_id,),
        ).fetchone()[0]
        cursor = conn.execute(
            """INSERT INTO aura_round_targets (round_id, student_name, sort_order)
               VALUES (?, ?, ?)""",
            (round_id, data.student_name.strip(), order),
        )
        # Historical monthly snapshots remain until explicitly regenerated.
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "studentName": data.student_name.strip(),
            "report": None,
        }


def delete_round_target(user_id: int, target_id: int, *, confirm: bool = False,
                        approved_price_change: tuple[int, int] | None = None):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT t.id, r.id AS round_id, r.progress_stage, e.start_time, e.end_time
               FROM aura_round_targets t
               JOIN aura_clinic_rounds r ON r.id = t.round_id
               JOIN events e ON e.id = r.event_id
               WHERE t.id = ? AND r.user_id = ?""",
            (target_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="학생 항목을 찾을 수 없습니다.")
        if not confirm:
            raise HTTPException(status_code=409, detail="학생 제거에는 명시적 확인이 필요합니다.")
        if conn.execute("SELECT 1 FROM aura_target_reports WHERE target_id = ?", (target_id,)).fetchone():
            raise HTTPException(status_code=409, detail="리포트가 있는 학생은 제거할 수 없습니다.")
        if _round_target_count(conn, row['round_id']) <= 1:
            raise HTTPException(status_code=409, detail="마지막 학생은 제거할 수 없습니다.")
        conn.execute("DELETE FROM aura_round_targets WHERE id = ?", (target_id,))
        # Keep historical snapshot bytes until separately approved regeneration.
        conn.commit()


def _default_template_document(school_name: str, progress_stage: str, round_number: int):
    now = datetime.now(timezone.utc).isoformat()

    def block(kind: str, text: str, level: int | None = None):
        result = {
            "id": f"block-{uuid4()}",
            "type": kind,
            "children": [{"type": "text", "text": text}],
        }
        if level:
            result["level"] = level
        return result

    return {
        "version": 1,
        "documentId": f"document-{uuid4()}",
        "createdAt": now,
        "updatedAt": now,
        "blocks": [
            block(
                "heading",
                f"{school_name} {STAGE_LABELS[progress_stage]} {round_number}회차 클리닉",
                1,
            ),
            block("heading", "관찰 내용", 2),
            block("paragraph", ""),
            block("heading", "보완할 부분", 2),
            block("paragraph", ""),
            block("heading", "다음 목표", 2),
            block("paragraph", ""),
        ],
    }


def _target_owner(conn, target_id: int, user_id: int):
    row = conn.execute(
        """SELECT t.*, r.id AS clinic_round_id, r.round_number,
                  r.round_numbers_json, r.progress_stage, r.school_id,
                  s.name AS school_name, e.start_time, e.end_time
           FROM aura_round_targets t
           JOIN aura_clinic_rounds r ON r.id = t.round_id
           JOIN aura_schools s ON s.id = r.school_id
           JOIN events e ON e.id = r.event_id
           WHERE t.id = ? AND r.user_id = ?""",
        (target_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="학생 리포트를 찾을 수 없습니다.")
    return row


def _combined_round_template(conn, user_id: int, target):
    round_numbers = json.loads(target["round_numbers_json"] or "[]") or [
        target["round_number"]
    ]
    documents = []
    templates = []
    for round_number in round_numbers:
        template = conn.execute(
            """SELECT * FROM aura_round_templates
               WHERE user_id = ? AND school_id = ? AND progress_stage = ?
                 AND round_number = ?
                 AND is_active = 1
               ORDER BY version DESC LIMIT 1""",
            (user_id, target["school_id"], target["progress_stage"], round_number),
        ).fetchone()
        if not template:
            # Only new midterm rounds inherit an old semester's active default.
            # The report snapshots the original template ID/version below;
            # final rounds and previously created reports never use this path.
            legacy_stage = next(
                (old for old, new in LEGACY_STAGE_ALIASES.items()
                 if new == target["progress_stage"]), None
            )
            if legacy_stage:
                template = conn.execute(
                    """SELECT * FROM aura_round_templates
                       WHERE user_id = ? AND school_id = ? AND progress_stage = ?
                         AND round_number = ? AND is_active = 1
                       ORDER BY version DESC LIMIT 1""",
                    (user_id, target["school_id"], legacy_stage, round_number),
                ).fetchone()
        templates.append(template)
        documents.append(
            json.loads(template["content_json"])
            if template
            else _default_template_document(
                target["school_name"], target["progress_stage"], round_number
            )
        )
    now = datetime.now(timezone.utc).isoformat()
    combined = {
        "version": 1,
        "documentId": f"document-{uuid4()}",
        "createdAt": now,
        "updatedAt": now,
        "blocks": [
            block
            for document in documents
            for block in document.get("blocks", [])
        ],
    }
    # Keep the editor's canonical document. Flattening only `blocks` drops
    # indentation, pasted text styles and highlight marks on new reports.
    def legacy_nodes(document):
        def text_node(block):
            content = []
            for chunk in block.get("children", []):
                text = chunk.get("text")
                if not text:
                    continue
                marks = [{"type": key} for key in ("bold", "italic", "underline", "strike", "code") if chunk.get(key)]
                if chunk.get("highlightColor"):
                    marks.append({"type": "highlight", "attrs": {"color": chunk["highlightColor"]}})
                if chunk.get("textColor"):
                    marks.append({"type": "textStyle", "attrs": {"color": chunk["textColor"]}})
                content.append({"type": "text", "text": text, "marks": marks})
            attrs = {"id": block.get("id"), "indent": block.get("depth", 0)}
            if block.get("type") == "heading":
                attrs["level"] = block.get("level", 1)
            kind = block.get("type", "paragraph")
            if kind in ("blockquote", "bulletList", "orderedList"):
                paragraph = {"type": "paragraph", "attrs": attrs, "content": content}
                if kind == "blockquote":
                    return {"type": kind, "content": [paragraph]}
                return {"type": kind, "content": [{"type": "listItem", "content": [paragraph]}]}
            return {"type": kind, "attrs": attrs, "content": content}

        nodes = []
        for block in document.get("blocks", []):
            if block.get("type") != "table":
                nodes.append(text_node(block))
            else:
                nodes.append({
                    "type": "table",
                    "attrs": {"id": block.get("id"), "indent": block.get("depth", 0)},
                    "content": [
                        {"type": "tableRow", "content": [
                            {"type": "tableCell", "attrs": {"id": cell.get("id")},
                             "content": [text_node(child) for child in cell.get("blocks", [])]}
                            for cell in row
                        ]}
                        for row in block.get("rows", [])
                    ],
                })
        return nodes

    combined["schemaVersion"] = 2
    combined["richContent"] = {
        "type": "doc",
        "content": [
            node
            for document in documents
            for node in (
                document["richContent"].get("content", [])
                if isinstance(document.get("richContent"), dict)
                and document["richContent"].get("type") == "doc"
                else legacy_nodes(document)
            )
        ],
    }
    return round_numbers, templates, combined


def get_or_create_target_report(user_id: int, target_id: int):
    with connection() as conn:
        target = _target_owner(conn, target_id, user_id)
        report = conn.execute(
            "SELECT * FROM aura_target_reports WHERE target_id = ?",
            (target_id,),
        ).fetchone()
        if not report:
            round_numbers, templates, content = _combined_round_template(
                conn, user_id, target
            )
            template = templates[0] if len(templates) == 1 else None
            conn.execute(
                """INSERT INTO aura_target_reports
                   (target_id, template_id, template_version, content_json)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(target_id) DO NOTHING""",
                (
                    target_id,
                    template["id"] if template else None,
                    template["version"] if template else None,
                    json.dumps(content, ensure_ascii=False),
                ),
            )
            conn.commit()
            report = conn.execute(
                "SELECT * FROM aura_target_reports WHERE target_id = ?",
                (target_id,),
            ).fetchone()
        content = json.loads(report["content_json"])
        siblings = conn.execute(
            """SELECT t.id, t.student_name, rp.status
               FROM aura_round_targets t
               JOIN aura_clinic_rounds sibling_round ON sibling_round.id = t.round_id
               JOIN events sibling_event ON sibling_event.id = sibling_round.event_id
               LEFT JOIN aura_target_reports rp ON rp.target_id = t.id
               WHERE sibling_round.user_id = ?
                 AND sibling_round.school_id = ?
                 AND sibling_round.progress_stage = ?
                 AND sibling_round.round_numbers_json = ?
               ORDER BY sibling_event.start_time, t.sort_order, t.id""",
            (
                user_id,
                target["school_id"],
                target["progress_stage"],
                target["round_numbers_json"],
            ),
        ).fetchall()
        round_numbers = json.loads(target["round_numbers_json"] or "[]") or [
            target["round_number"]
        ]
        return {
            "id": report["id"],
            "targetId": target_id,
            "studentName": target["student_name"],
            "schoolId": target["school_id"],
            "schoolName": target["school_name"],
            "progressStage": target["progress_stage"],
            "roundNumber": target["round_number"],
            "roundNumbers": round_numbers,
            "roundLabel": f"{','.join(str(number) for number in round_numbers)}회차",
            "startTime": target["start_time"],
            "endTime": target["end_time"],
            "templateVersion": report["template_version"],
            "contentJson": content,
            "analysisJson": _analysis_document(content),
            "sourceNotes": report["source_notes"],
            "questionChecks": json.loads(report["question_checks_json"] or "{}"),
            "lectureProgress": report["lecture_progress"],
            "lectureComprehension": report["lecture_comprehension"],
            "memoryBefore": report["memory_before"],
            "memoryAfter": report["memory_after"],
            "assessmentJson": json.loads(report["assessment_json"] or "{}"),
            "generatedReportJson": (
                json.loads(report["generated_report_json"])
                if report["generated_report_json"] else None
            ),
            "aiModel": report["ai_model"],
            "clinicTargets": [
                {
                    "id": item["id"],
                    "studentName": item["student_name"],
                    "status": item["status"] or "unwritten",
                }
                for item in siblings
            ],
            "status": report["status"],
            "submittedAt": report["submitted_at"],
        }


def list_target_report_attachments(user_id: int, target_id: int):
    with connection() as conn:
        report = get_or_create_target_report(user_id, target_id)
        rows = conn.execute(
            """SELECT id, kind, original_name, mime_type, byte_size, created_at
               FROM aura_report_attachments
               WHERE user_id = ? AND target_report_id = ? ORDER BY id""",
            (user_id, report["id"]),
        ).fetchall()
        return [
            {
                "id": row["id"], "kind": row["kind"], "name": row["original_name"],
                "mimeType": row["mime_type"], "byteSize": row["byte_size"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]


def save_target_report_attachment(
    user_id: int, target_id: int, kind: str, filename: str, mime_type: str, payload: bytes
):
    if kind not in ATTACHMENT_KINDS:
        raise HTTPException(status_code=400, detail="첨부 분류를 확인해주세요.")
    if not payload or len(payload) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="이미지는 파일당 15MB 이하로 올려주세요.")
    if not mime_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="이미지 파일만 첨부할 수 있습니다.")
    report = get_or_create_target_report(user_id, target_id)
    # Avoid creating a temporary file/directory for an already completed report.
    # The transactional status check below remains necessary for concurrent submits.
    if report["status"] == "submitted":
        raise HTTPException(status_code=409, detail="제출된 리포트의 첨부는 변경할 수 없습니다.")
    suffix = ".jpg" if mime_type == "image/jpeg" else ".png" if mime_type == "image/png" else ".webp"
    storage_name = f"{uuid4().hex}{suffix}"
    directory = ATTACHMENT_ROOT / str(user_id) / str(report["id"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / storage_name
    path.write_bytes(payload)
    try:
        with connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute(
                "SELECT COUNT(*) FROM aura_report_attachments WHERE target_report_id = ? AND kind = ?",
                (report["id"], kind),
            ).fetchone()[0]
            if count >= 30:
                raise HTTPException(status_code=400, detail="분류별 사진은 최대 30장까지 첨부할 수 있습니다.")
            status = conn.execute(
                "SELECT status FROM aura_target_reports WHERE id = ?", (report["id"],)
            ).fetchone()
            if status["status"] == "submitted":
                raise HTTPException(status_code=409, detail="제출된 리포트의 첨부는 변경할 수 없습니다.")
            cursor = conn.execute(
                """INSERT INTO aura_report_attachments
                   (user_id, target_report_id, kind, original_name, mime_type, storage_name, byte_size)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, report["id"], kind, filename[:200], mime_type, storage_name, len(payload)),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "kind": kind, "name": filename, "mimeType": mime_type}
    except Exception:
        path.unlink(missing_ok=True)
        raise


def read_target_report_attachment(user_id: int, attachment_id: int):
    with connection() as conn:
        row = conn.execute(
            """SELECT id, mime_type, original_name, storage_name, target_report_id
               FROM aura_report_attachments WHERE id = ? AND user_id = ?""",
            (attachment_id, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="첨부 이미지를 찾을 수 없습니다.")
    path = ATTACHMENT_ROOT / str(user_id) / str(row["target_report_id"]) / row["storage_name"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="첨부 이미지 파일을 찾을 수 없습니다.")
    return path, row["mime_type"], row["original_name"]


def delete_target_report_attachment(user_id: int, attachment_id: int):
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT a.id, a.user_id, a.byte_size, a.storage_name, a.target_report_id, rp.status
               FROM aura_report_attachments a
               JOIN aura_target_reports rp ON rp.id = a.target_report_id
               WHERE a.id = ? AND a.user_id = ?""", (attachment_id, user_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="첨부 이미지를 찾을 수 없습니다.")
        if row["status"] == "submitted":
            raise HTTPException(status_code=409, detail="제출된 리포트의 첨부는 변경할 수 없습니다.")
        journal_id = _journal_attachment(conn, row, "attachment")
        conn.execute("DELETE FROM aura_report_attachments WHERE id = ?", (attachment_id,))
        conn.commit()
    _remove_attachment_files([journal_id])


def _attachment_files_for_parent(conn, user_id: int, *, school_id: int | None = None,
                                 round_id: int | None = None):
    """Capture owner-scoped file references before the FK cascade erases them."""
    if (school_id is None) == (round_id is None):
        raise ValueError("Exactly one parent is required")
    predicate = "r.school_id = ?" if school_id is not None else "r.id = ?"
    rows = conn.execute(
        f"""SELECT a.id, a.user_id, a.target_report_id, a.storage_name, a.byte_size
            FROM aura_report_attachments a
            JOIN aura_target_reports rp ON rp.id = a.target_report_id
            JOIN aura_round_targets t ON t.id = rp.target_id
            JOIN aura_clinic_rounds r ON r.id = t.round_id
            WHERE r.user_id = ? AND a.user_id = ? AND {predicate}""",
        (user_id, user_id, school_id if school_id is not None else round_id),
    ).fetchall()
    return rows


def _journal_attachment(conn, row, reason: str):
    fingerprint = attachment_cleanup.snapshot(
        ATTACHMENT_ROOT, row["user_id"], row["target_report_id"], row["storage_name"]
    )
    return conn.execute(
        """INSERT INTO aura_attachment_cleanup_journal
           (user_id, target_report_id, attachment_id, storage_name, byte_size, file_sha256, reason)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (row["user_id"], row["target_report_id"], row["id"], row["storage_name"],
         row["byte_size"], fingerprint, reason),
    ).lastrowid


def _journal_parent_files(conn, user_id: int, reason: str, **scope):
    rows = _attachment_files_for_parent(conn, user_id, **scope)
    return [_journal_attachment(conn, row, reason) for row in rows]


def dry_run_attachment_cleanup(journal_id: int):
    """Internal-only diagnostic; never expose via student API or sweep automatically."""
    with connection() as conn:
        return attachment_cleanup.assess(conn, ATTACHMENT_ROOT, journal_id)


def _remove_attachment_files(files):
    """Best-effort cleanup of the just-committed request, NOT an operating retry."""
    for journal_id in files:
        with connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            completed = conn.execute("SELECT status FROM aura_attachment_cleanup_journal WHERE id=?", (journal_id,)).fetchone()
            if completed and completed["status"] == "completed":
                conn.commit()
                continue
            assessment = attachment_cleanup.assess(conn, ATTACHMENT_ROOT, journal_id)
            if assessment["classification"] == "missing":
                conn.execute("UPDATE aura_attachment_cleanup_journal SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'", (journal_id,))
                conn.commit()
                continue
            if assessment["classification"] != "safe":
                raise HTTPException(status_code=500, detail="삭제는 완료됐으나 첨부 파일 정리가 검증되지 않아 보류되었습니다.")
            row = conn.execute("SELECT * FROM aura_attachment_cleanup_journal WHERE id=? AND status='pending'", (journal_id,)).fetchone()
            directory = ATTACHMENT_ROOT / str(row["user_id"]) / str(row["target_report_id"])
            opened = []
            try:
                fd = os.open(ATTACHMENT_ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                opened.append(fd)
                for component in (str(row["user_id"]), str(row["target_report_id"])):
                    fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    opened.append(fd)
                file_fd = os.open(row["storage_name"], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                opened.append(file_fd)
                actual = os.fstat(file_fd)
                current = os.stat(row["storage_name"], dir_fd=fd, follow_symlinks=False)
                if (not stat.S_ISREG(actual.st_mode) or actual.st_ino != current.st_ino
                        or actual.st_dev != current.st_dev
                        or attachment_cleanup._fingerprint(ATTACHMENT_ROOT, row["user_id"], row["target_report_id"], row["storage_name"]) != (row["byte_size"], row["file_sha256"])):
                    raise OSError("candidate changed")
                os.unlink(row["storage_name"], dir_fd=fd)
            except OSError as exc:
                raise HTTPException(status_code=500, detail="삭제는 완료됐으나 첨부 파일 정리가 보류되었습니다.") from exc
            finally:
                for fd in reversed(opened):
                    os.close(fd)
            conn.execute("UPDATE aura_attachment_cleanup_journal SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'", (journal_id,))
            conn.commit()
        try:
            directory.rmdir()
        except OSError:
            pass


def update_target_report(user_id: int, report_id: int, data, submit: bool = False):
    values = data.model_dump(exclude_unset=True) if data else {}
    submit = submit or values.get("status") == "submitted"
    if submit:
        # Retry only this owned report's previously journalled candidates.
        with connection() as conn:
            owned = conn.execute("""SELECT 1 FROM aura_target_reports rp
                JOIN aura_round_targets t ON t.id = rp.target_id
                JOIN aura_clinic_rounds r ON r.id = t.round_id
                WHERE rp.id = ? AND r.user_id = ?""", (report_id, user_id)).fetchone()
            if not owned:
                raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
            pending = [row[0] for row in conn.execute(
                "SELECT id FROM aura_attachment_cleanup_journal WHERE user_id=? AND target_report_id=? AND status='pending'",
                (user_id, report_id)).fetchall()]
        if pending:
            _remove_attachment_files(pending)
    if data:
        values["has_user_edits"] = 1
    if values.get("status") in {"draft", "ready"}:
        values["submitted_at"] = None
    if "content_json" in values:
        values["content_json"] = json.dumps(
            values["content_json"], ensure_ascii=False
        )
    if "question_checks" in values:
        values["question_checks_json"] = json.dumps(
            values.pop("question_checks"), ensure_ascii=False
        )
    for json_field in ("assessment_json", "generated_report_json"):
        if json_field in values:
            values[json_field] = json.dumps(values[json_field], ensure_ascii=False)
    if submit:
        values["status"] = "submitted"
        values["submitted_at"] = datetime.now(timezone.utc).isoformat()

    cleanup_ids = []
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT rp.target_id FROM aura_target_reports rp
               JOIN aura_round_targets t ON t.id = rp.target_id
               JOIN aura_clinic_rounds r ON r.id = t.round_id
               WHERE rp.id = ? AND r.user_id = ?""",
            (report_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
        if submit and conn.execute(
            """SELECT 1 FROM aura_attachment_cleanup_journal
               WHERE user_id = ? AND target_report_id = ? AND status = 'pending' LIMIT 1""",
            (user_id, report_id),
        ).fetchone():
            raise HTTPException(status_code=500, detail="이 리포트의 첨부 파일 정리가 보류되어 작성 완료를 확인할 수 없습니다.")
        if values:
            sets = ", ".join(f"{key} = ?" for key in values)
            conn.execute(
                f"UPDATE aura_target_reports SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (*values.values(), report_id),
            )
        if submit:
            submitted = conn.execute(
                """SELECT rp.assessment_json, r.school_id, r.progress_stage,
                          r.round_numbers_json
                   FROM aura_target_reports rp
                   JOIN aura_round_targets t ON t.id = rp.target_id
                   JOIN aura_clinic_rounds r ON r.id = t.round_id
                   WHERE rp.id = ?""",
                (report_id,),
            ).fetchone()
            assessment = json.loads(submitted["assessment_json"] or "{}")
            items = [
                str(item.get("name", "")).strip()
                for item in assessment.get("items", [])
                if str(item.get("name", "")).strip()
            ]
            round_key = ",".join(
                str(number)
                for number in json.loads(submitted["round_numbers_json"] or "[]")
            )
            existing = conn.execute(
                """SELECT id, items_json FROM clinic_report_score_formats
                   WHERE school_id = ? AND progress_stage = ?
                     AND round_key = ? AND is_active = 1
                   LIMIT 1""",
                (submitted["school_id"], submitted["progress_stage"], round_key),
            ).fetchone()
            if existing:
                # 기존 학교·회차 양식은 다음 리포트의 기본값으로만 유지한다.
                # 최종 PDF 단계의 학생별 CSV 수정은 양식 자체를 덮어쓰지 않는다.
                pass
            if items and not existing:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """INSERT INTO clinic_report_score_formats
                       (user_id, school_id, progress_stage, round_key, name, items_json, source,
                        is_active, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'manual', 1, ?, ?)""",
                    (
                        user_id,
                        submitted["school_id"],
                        submitted["progress_stage"],
                        round_key,
                        str(assessment.get("formatName") or "학습 내용 및 암기 정도 평가"),
                        json.dumps(items, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
            attachments = conn.execute(
                """SELECT a.id, a.user_id, a.target_report_id, a.storage_name, a.byte_size
                   FROM aura_report_attachments a
                   WHERE a.user_id = ? AND a.target_report_id = ?
                     AND (SELECT COUNT(*) FROM aura_report_attachments refs
                          WHERE refs.storage_name = a.storage_name) = 1""",
                (user_id, report_id),
            ).fetchall()
            for attachment in attachments:
                cleanup_ids.append(_journal_attachment(conn, attachment, "attachment"))
                conn.execute("DELETE FROM aura_report_attachments WHERE id = ? AND user_id = ?",
                             (attachment["id"], user_id))
        conn.commit()
    _remove_attachment_files(cleanup_ids)
    return get_or_create_target_report(user_id, row["target_id"])


def save_round_template(user_id: int, school_id: int, round_number: int, data):
    with connection() as conn:
        school = _owned_row(conn, "aura_schools", school_id, user_id)
        current = conn.execute(
            """SELECT COALESCE(MAX(version), 0) FROM aura_round_templates
               WHERE school_id = ? AND progress_stage = ? AND round_number = ?""",
            (school_id, data.progress_stage, round_number),
        ).fetchone()[0]
        conn.execute(
            """UPDATE aura_round_templates SET is_active = 0
               WHERE school_id = ? AND progress_stage = ? AND round_number = ?""",
            (school_id, data.progress_stage, round_number),
        )
        cursor = conn.execute(
            """INSERT INTO aura_round_templates
               (user_id, school_id, progress_stage, round_number, version, content_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                school_id,
                data.progress_stage,
                round_number,
                current + 1,
                json.dumps(data.content_json, ensure_ascii=False),
            ),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "schoolId": school_id,
            "schoolName": school["name"],
            "progressStage": data.progress_stage,
            "roundNumber": round_number,
            "version": current + 1,
        }


def school_settlements(user_id: int, year: int, month: int):
    with connection() as conn:
        row = conn.execute(
            """SELECT data_json, generated_at, pricing_version FROM aura_settlement_snapshots
               WHERE user_id = ? AND year = ? AND month = ?""",
            (user_id, year, month),
        ).fetchone()
    if not row or row["pricing_version"] < 6:
        return {
            "year": year,
            "month": month,
            "totalAmount": 0,
            "completedCount": 0,
            "settlementCount": 0,
            "items": [],
            "generatedAt": None,
        }
    result = json.loads(row["data_json"])
    result["generatedAt"] = row["generated_at"]
    return result


def generate_school_settlements(user_id: int, year: int, month: int, approval: dict | None = None):
    start = f"{year:04d}-{month:02d}-01"
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = f"{next_year:04d}-{next_month:02d}-01"
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        query = _round_query() + " WHERE r.user_id = ? AND e.start_time >= ? AND e.start_time < ? ORDER BY s.name, r.round_number, e.start_time"
        items = [
            item for row in conn.execute(query, (user_id, start, end)).fetchall()
            if (item := _round_dict(conn, row))["attendanceStatus"] != "cancelled"
        ]
        # This explicit calculation action never requires a separate approval.
        for item in items:
            participant_count = len(item["targets"])
            item["hourlyRate"] = clinic_hourly_cost(item["progressStage"], participant_count)
            item["amount"] = clinic_settlement_amount(
                item["progressStage"],
                datetime.fromisoformat(item["startTime"].replace("Z", "+00:00")),
                datetime.fromisoformat(item["endTime"].replace("Z", "+00:00")),
                participant_count,
            )
        for item in items:
            conn.execute("UPDATE aura_clinic_rounds SET hourly_rate=?,amount=? WHERE id=? AND user_id=?",
                         (item["hourlyRate"], item["amount"], item["id"], user_id))
        result = {
            "year": year,
            "month": month,
            "totalAmount": sum(item["amount"] for item in items),
            "completedCount": sum(item["attendanceStatus"] == "completed" for item in items),
            "settlementCount": len(items),
            "items": items,
        }
        conn.execute(
            """INSERT INTO aura_settlement_snapshots
                   (user_id, year, month, data_json, pricing_version, generated_at)
               VALUES (?, ?, ?, ?, 6, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, year, month) DO UPDATE SET
                   data_json = excluded.data_json,
                   pricing_version = excluded.pricing_version,
                   generated_at = CURRENT_TIMESTAMP""",
            (user_id, year, month, json.dumps(result, ensure_ascii=False)),
        )
        conn.commit()
        generated_at = conn.execute(
            """SELECT generated_at FROM aura_settlement_snapshots
               WHERE user_id = ? AND year = ? AND month = ?""",
            (user_id, year, month),
        ).fetchone()["generated_at"]
    result["generatedAt"] = generated_at
    return result
