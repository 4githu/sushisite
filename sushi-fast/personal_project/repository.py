import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from .db import connection


def _calculated_amount(hourly_rate: int, start: datetime, end: datetime | None) -> int:
    if end is None:
        return hourly_rate
    minutes = max(0, int((end - start).total_seconds() // 60))
    return round(hourly_rate * minutes / 60)


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
             AND (
               e.end_time IS NULL
               OR julianday(e.end_time) - julianday(e.start_time) <= 0.5
             )
             AND e.start_time < ?
             AND COALESCE(e.end_time, e.start_time) > ?
             AND (? IS NULL OR e.id != ?)
           ORDER BY e.start_time""",
        (user_id, effective_end.isoformat(), start.isoformat(), exclude_event_id, exclude_event_id),
    ).fetchall()
    return [
        {
            "eventId": row["id"],
            "title": row["title"],
            "studentName": row["student_name"],
            "startTime": row["start_time"],
            "endTime": row["end_time"],
        }
        for row in rows
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
                """SELECT school_id FROM aura_clinic_rounds
                   WHERE event_id = ? AND user_id = ?""",
                (event_id, user_id),
            ).fetchone()
            result["serviceLink"] = (
                f"/personal-project/aura/schools/{clinic_round['school_id']}"
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
        if values.get("attendance_status") == "completed":
            conn.execute(
                "UPDATE events SET status = 'done', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session["event_id"],),
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
            if not submit:
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
    return {
        "id": row["id"],
        "name": row["name"],
        "defaultHourlyRate": row["default_hourly_rate"],
        "memo": row["memo"],
        "isActive": bool(row["is_active"]),
        "roundCount": round_count,
        "priority": row["priority"],
        "termStatus": row["term_status"],
    }


def list_schools(user_id: int):
    with connection() as conn:
        rows = conn.execute(
            """SELECT s.*, COUNT(r.id) AS round_count
               FROM aura_schools s
               LEFT JOIN aura_clinic_rounds r ON r.school_id = s.id
               WHERE s.user_id = ?
               GROUP BY s.id
               ORDER BY (s.term_status = 'active') DESC, s.priority DESC,
                        s.is_active DESC, s.name""",
            (user_id,),
        ).fetchall()
        return [_school_dict(row, row["round_count"]) for row in rows]


def create_school(user_id: int, data):
    value = data.model_dump()
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
                   (user_id, name, default_hourly_rate, memo, priority)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    user_id,
                    value["name"].strip(),
                    value["default_hourly_rate"],
                    value["memo"],
                    value["priority"],
                ),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=409, detail="이미 등록된 학교 이름입니다.") from exc
        return _school_dict(
            _owned_row(conn, "aura_schools", cursor.lastrowid, user_id)
        )


def update_school(user_id: int, school_id: int, data):
    values = data.model_dump(exclude_unset=True)
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
                    status_code=409, detail="이미 등록된 학교 이름입니다."
                ) from exc
        return _school_dict(_owned_row(conn, "aura_schools", school_id, user_id))


def move_school(user_id: int, school_id: int, direction: str):
    if direction not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="이동 방향을 확인해주세요.")
    with connection() as conn:
        current = _owned_row(conn, "aura_schools", school_id, user_id)
        schools = conn.execute(
            """SELECT * FROM aura_schools
               WHERE user_id = ? AND term_status = ?
               ORDER BY priority DESC, name""",
            (user_id, current["term_status"]),
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


def delete_school(user_id: int, school_id: int):
    with connection() as conn:
        _owned_row(conn, "aura_schools", school_id, user_id)
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
        "eventId": row["event_id"],
        "roundNumber": row["round_number"],
        "roundNumbers": round_numbers,
        "roundLabel": f"{','.join(str(number) for number in round_numbers)}회차",
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "description": row["description"],
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
        SELECT r.*, s.name AS school_name, e.start_time, e.end_time,
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
            """SELECT round_number, version, content_json, is_active, created_at
               FROM aura_round_templates
               WHERE user_id = ? AND school_id = ?
               ORDER BY round_number, version""",
            (user_id, school_id),
        ).fetchall()
        reports = conn.execute(
            """SELECT t.student_name, r.round_numbers_json, rp.template_version,
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
        hourly_rate = (
            data.hourly_rate
            if data.hourly_rate is not None
            else school["default_hourly_rate"]
        )
        amount = _calculated_amount(hourly_rate, data.start_time, data.end_time)
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
                    hourly_rate, amount, round_numbers_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    data.school_id,
                    event.lastrowid,
                    data.round_number,
                    data.report_required,
                    hourly_rate,
                    amount,
                    json.dumps([data.round_number]),
                ),
            )
            for index, name in enumerate(data.student_names):
                conn.execute(
                    """INSERT INTO aura_round_targets
                       (round_id, student_name, sort_order)
                       VALUES (?, ?, ?)""",
                    (round_cursor.lastrowid, name, index),
                )
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

        hourly_rate = (
            data.hourly_rate
            if data.hourly_rate is not None
            else school["default_hourly_rate"]
        )
        amount = _calculated_amount(hourly_rate, data.start_time, data.end_time)
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
                        series_group_id, series_index)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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


def update_clinic_round(user_id: int, round_id: int, data):
    values = data.model_dump(exclude_unset=True, mode="json")
    allow_overlap = values.pop("allow_overlap", False)
    scope = values.pop("scope", "this")
    student_names = values.pop("student_names", None)
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
        current = _owned_row(conn, "aura_clinic_rounds", round_id, user_id)
        requested_school = (
            _owned_row(conn, "aura_schools", requested_school_id, user_id)
            if requested_school_id is not None
            else _owned_row(conn, "aura_schools", current["school_id"], user_id)
        )
        event = _owned_row(conn, "events", current["event_id"], user_id)
        start = data.start_time or datetime.fromisoformat(
            event["start_time"].replace("Z", "+00:00")
        )
        end = (
            data.end_time
            if "end_time" in event_values
            else datetime.fromisoformat(event["end_time"].replace("Z", "+00:00"))
        )
        if end <= start or end - start > timedelta(hours=12):
            raise HTTPException(status_code=400, detail="클리닉 시간을 확인해주세요.")
        if time_changed and not allow_overlap:
            _raise_conflict(
                _conflicting_events(
                    conn, user_id, start, end, current["event_id"]
                )
            )
        hourly_rate = (
            data.hourly_rate
            if data.hourly_rate is not None
            else current["hourly_rate"]
        )
        if time_changed or data.hourly_rate is not None:
            values["amount"] = _calculated_amount(hourly_rate, start, end)
        rounds = [current]
        if scope == "following" and current["series_group_id"]:
            rounds = conn.execute(
                """SELECT * FROM aura_clinic_rounds
                   WHERE user_id = ? AND series_group_id = ? AND series_index >= ?
                   ORDER BY series_index""",
                (user_id, current["series_group_id"], current["series_index"]),
            ).fetchall()
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
        start_delta = start - datetime.fromisoformat(
            event["start_time"].replace("Z", "+00:00")
        )
        duration = end - start
        for item in rounds:
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
                item_event = _owned_row(conn, "events", item["event_id"], user_id)
                item_start = datetime.fromisoformat(
                    item_event["start_time"].replace("Z", "+00:00")
                )
                item_end = datetime.fromisoformat(
                    item_event["end_time"].replace("Z", "+00:00")
                )
                if time_changed or data.hourly_rate is not None:
                    target_start = item_start + start_delta
                    target_end = target_start + duration
                    item_values["amount"] = _calculated_amount(
                        hourly_rate, target_start, target_end
                    )
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
                    item_start = datetime.fromisoformat(
                        item_event["start_time"].replace("Z", "+00:00")
                    )
                    target_start = item_start + start_delta
                    target_end = target_start + duration
                    item_event_values["start_time"] = target_start.isoformat()
                    item_event_values["end_time"] = target_end.isoformat()
                sets = ", ".join(f"{key} = ?" for key in item_event_values)
                conn.execute(
                    f"""UPDATE events SET {sets},
                        updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (*item_event_values.values(), item["event_id"]),
                )
            if requested_school_id is not None or requested_round_number is not None:
                target_round_label = ",".join(str(number) for number in target_numbers)
                conn.execute(
                    "UPDATE events SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        f"{requested_school['name']} {target_round_label}회차 클리닉",
                        item["event_id"],
                    ),
                )
            if student_names is not None:
                targets = conn.execute(
                    """SELECT id FROM aura_round_targets
                       WHERE round_id = ? ORDER BY sort_order, id""",
                    (item["id"],),
                ).fetchall()
                for index, name in enumerate(student_names):
                    if index < len(targets):
                        conn.execute(
                            """UPDATE aura_round_targets
                               SET student_name = ?, sort_order = ? WHERE id = ?""",
                            (name, index, targets[index]["id"]),
                        )
                    else:
                        conn.execute(
                            """INSERT INTO aura_round_targets
                               (round_id, student_name, sort_order)
                               VALUES (?, ?, ?)""",
                            (item["id"], name, index),
                        )
                for target in targets[len(student_names):]:
                    conn.execute(
                        "DELETE FROM aura_round_targets WHERE id = ?",
                        (target["id"],),
                    )
            if requested_round_number is not None:
                conn.execute(
                    """DELETE FROM aura_target_reports
                       WHERE has_user_edits = 0
                         AND target_id IN (
                           SELECT id FROM aura_round_targets WHERE round_id = ?
                         )""",
                    (item["id"],),
                )
            if values.get("attendance_status") == "completed":
                conn.execute(
                    "UPDATE events SET status = 'done' WHERE id = ?",
                    (item["event_id"],),
                )
        conn.commit()
    return get_clinic_round(user_id, round_id)


def delete_clinic_round(user_id: int, round_id: int):
    with connection() as conn:
        current = _owned_row(conn, "aura_clinic_rounds", round_id, user_id)
        conn.execute(
            "DELETE FROM events WHERE id = ? AND user_id = ?",
            (current["event_id"], user_id),
        )
        conn.commit()


def add_round_target(user_id: int, round_id: int, data):
    with connection() as conn:
        _owned_row(conn, "aura_clinic_rounds", round_id, user_id)
        order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM aura_round_targets WHERE round_id = ?",
            (round_id,),
        ).fetchone()[0]
        cursor = conn.execute(
            """INSERT INTO aura_round_targets (round_id, student_name, sort_order)
               VALUES (?, ?, ?)""",
            (round_id, data.student_name.strip(), order),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "studentName": data.student_name.strip(),
            "report": None,
        }


def delete_round_target(user_id: int, target_id: int):
    with connection() as conn:
        row = conn.execute(
            """SELECT t.id FROM aura_round_targets t
               JOIN aura_clinic_rounds r ON r.id = t.round_id
               WHERE t.id = ? AND r.user_id = ?""",
            (target_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="학생 항목을 찾을 수 없습니다.")
        conn.execute("DELETE FROM aura_round_targets WHERE id = ?", (target_id,))
        conn.commit()


def _default_template_document(school_name: str, round_number: int):
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
            block("heading", f"{school_name} {round_number}회차 클리닉", 1),
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
                  r.round_numbers_json, r.school_id,
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
               WHERE user_id = ? AND school_id = ? AND round_number = ?
                 AND is_active = 1
               ORDER BY version DESC LIMIT 1""",
            (user_id, target["school_id"], round_number),
        ).fetchone()
        templates.append(template)
        documents.append(
            json.loads(template["content_json"])
            if template
            else _default_template_document(target["school_name"], round_number)
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
            cursor = conn.execute(
                """INSERT INTO aura_target_reports
                   (target_id, template_id, template_version, content_json)
                   VALUES (?, ?, ?, ?)""",
                (
                    target_id,
                    template["id"] if template else None,
                    template["version"] if template else None,
                    json.dumps(content, ensure_ascii=False),
                ),
            )
            conn.commit()
            report = conn.execute(
                "SELECT * FROM aura_target_reports WHERE id = ?",
                (cursor.lastrowid,),
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
                 AND sibling_round.round_numbers_json = ?
               ORDER BY sibling_event.start_time, t.sort_order, t.id""",
            (user_id, target["school_id"], target["round_numbers_json"]),
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


def update_target_report(user_id: int, report_id: int, data, submit: bool = False):
    values = data.model_dump(exclude_unset=True) if data else {}
    if data:
        values["has_user_edits"] = 1
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
    with connection() as conn:
        row = conn.execute(
            """SELECT rp.target_id FROM aura_target_reports rp
               JOIN aura_round_targets t ON t.id = rp.target_id
               JOIN aura_clinic_rounds r ON r.id = t.round_id
               WHERE rp.id = ? AND r.user_id = ?""",
            (report_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")
        if values:
            sets = ", ".join(f"{key} = ?" for key in values)
            conn.execute(
                f"UPDATE aura_target_reports SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (*values.values(), report_id),
            )
            conn.commit()
        if submit:
            submitted = conn.execute(
                """SELECT rp.assessment_json, r.school_id, r.round_numbers_json
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
                   WHERE school_id = ? AND round_key = ? AND is_active = 1
                   LIMIT 1""",
                (submitted["school_id"], round_key),
            ).fetchone()
            if existing:
                # 기존 학교·회차 양식은 다음 리포트의 기본값으로만 유지한다.
                # 최종 PDF 단계의 학생별 CSV 수정은 양식 자체를 덮어쓰지 않는다.
                pass
            if items and not existing:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """INSERT INTO clinic_report_score_formats
                       (user_id, school_id, round_key, name, items_json, source,
                        is_active, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, 'manual', 1, ?, ?)""",
                    (
                        user_id,
                        submitted["school_id"],
                        round_key,
                        str(assessment.get("formatName") or "학습 내용 및 암기 정도 평가"),
                        json.dumps(items, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
            conn.commit()
        return get_or_create_target_report(user_id, row["target_id"])


def save_round_template(user_id: int, school_id: int, round_number: int, data):
    with connection() as conn:
        school = _owned_row(conn, "aura_schools", school_id, user_id)
        current = conn.execute(
            """SELECT COALESCE(MAX(version), 0) FROM aura_round_templates
               WHERE school_id = ? AND round_number = ?""",
            (school_id, round_number),
        ).fetchone()[0]
        conn.execute(
            """UPDATE aura_round_templates SET is_active = 0
               WHERE school_id = ? AND round_number = ?""",
            (school_id, round_number),
        )
        cursor = conn.execute(
            """INSERT INTO aura_round_templates
               (user_id, school_id, round_number, version, content_json)
               VALUES (?, ?, ?, ?, ?)""",
            (
                user_id,
                school_id,
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
            "roundNumber": round_number,
            "version": current + 1,
        }


def school_settlements(user_id: int, year: int, month: int):
    start = f"{year:04d}-{month:02d}-01"
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = f"{next_year:04d}-{next_month:02d}-01"
    items = [
        item
        for item in list_clinic_rounds(user_id, None, start, end)
        if item["attendanceStatus"] == "completed"
    ]
    return {
        "year": year,
        "month": month,
        "totalAmount": sum(item["amount"] for item in items),
        "completedCount": len(items),
        "items": items,
    }
