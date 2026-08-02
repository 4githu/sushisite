from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any

from .config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS gemini_context_caches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    cache_name TEXT NOT NULL,
    expires_at TEXT,
    last_used_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(cache_key, model, prompt_hash)
);
CREATE INDEX IF NOT EXISTS idx_gemini_caches_lookup
    ON gemini_context_caches(cache_key, model, prompt_hash);

CREATE TABLE IF NOT EXISTS clinic_report_generation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER REFERENCES aura_round_targets(id) ON DELETE SET NULL,
    model TEXT NOT NULL,
    cache_mode TEXT NOT NULL CHECK(cache_mode IN ('implicit', 'explicit')),
    prompt_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('started', 'completed', 'failed')),
    response_text TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_clinic_report_runs_target
    ON clinic_report_generation_runs(target_id, created_at DESC);

CREATE TABLE IF NOT EXISTS clinic_report_score_formats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    school_id INTEGER NOT NULL REFERENCES aura_schools(id) ON DELETE CASCADE,
    round_key TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    items_json TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'generated'
        CHECK(source IN ('generated', 'manual')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clinic_score_formats_school
    ON clinic_report_score_formats(school_id, is_active, updated_at DESC);

CREATE TABLE IF NOT EXISTS clinic_report_generation_settings (
    user_id INTEGER NOT NULL,
    school_id INTEGER NOT NULL REFERENCES aura_schools(id) ON DELETE CASCADE,
    score_mode TEXT NOT NULL DEFAULT 'auto'
        CHECK(score_mode IN ('auto', 'none')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, school_id)
);
"""


@dataclass(frozen=True)
class CacheRecord:
    id: int
    cache_name: str
    expires_at: str | None


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"기존 개인 프로젝트 DB를 찾을 수 없습니다: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(clinic_report_generation_runs)")
        }
        additions = {
            "input_json": "TEXT",
            "response_json": "TEXT",
            "score_mode": "TEXT NOT NULL DEFAULT 'auto'",
            "score_format_id": "INTEGER",
            "provider": "TEXT NOT NULL DEFAULT 'gemini'",
            "input_hash": "TEXT",
        }
        for name, declaration in additions.items():
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE clinic_report_generation_runs ADD COLUMN {name} {declaration}"
                )
        score_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(clinic_report_score_formats)")
        }
        if "round_key" not in score_columns:
            conn.execute(
                "ALTER TABLE clinic_report_score_formats "
                "ADD COLUMN round_key TEXT NOT NULL DEFAULT ''"
            )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_clinic_score_formats_round
               ON clinic_report_score_formats(school_id, round_key, is_active, updated_at DESC)"""
        )
        conn.commit()


def get_cache(cache_key: str, model: str, prompt_hash: str) -> CacheRecord | None:
    with connect() as conn:
        row = conn.execute(
            """SELECT id, cache_name, expires_at
               FROM gemini_context_caches
               WHERE cache_key = ? AND model = ? AND prompt_hash = ?""",
            (cache_key, model, prompt_hash),
        ).fetchone()
    return CacheRecord(**dict(row)) if row else None


def save_cache(
    cache_key: str,
    model: str,
    prompt_hash: str,
    cache_name: str,
    expires_at: str | None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            """INSERT INTO gemini_context_caches
               (cache_key, model, prompt_hash, cache_name, expires_at,
                last_used_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(cache_key, model, prompt_hash) DO UPDATE SET
                 cache_name = excluded.cache_name,
                 expires_at = excluded.expires_at,
                 last_used_at = excluded.last_used_at,
                 updated_at = excluded.updated_at""",
            (cache_key, model, prompt_hash, cache_name, expires_at, now, now, now),
        )
        conn.commit()


def touch_cache(record_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            "UPDATE gemini_context_caches SET last_used_at = ?, updated_at = ? WHERE id = ?",
            (now, now, record_id),
        )
        conn.commit()


def delete_cache(record_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM gemini_context_caches WHERE id = ?", (record_id,))
        conn.commit()


def build_report_input(target_id: int) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            """SELECT t.student_name, r.user_id, s.id AS school_id,
                      s.name AS school_name,
                      r.round_numbers_json, e.start_time, e.end_time,
                      e.description, rp.source_notes, rp.question_checks_json,
                      rp.content_json
               FROM aura_round_targets t
               JOIN aura_clinic_rounds r ON r.id = t.round_id
               JOIN aura_schools s ON s.id = r.school_id
               JOIN events e ON e.id = r.event_id
               LEFT JOIN aura_target_reports rp ON rp.target_id = t.id
               WHERE t.id = ?""",
            (target_id,),
        ).fetchone()
    if not row:
        raise ValueError(f"target_id={target_id}인 학생 리포트를 찾을 수 없습니다.")
    rounds = json.loads(row["round_numbers_json"] or "[]")
    checks = json.loads(row["question_checks_json"] or "{}")
    document = (
        json.loads(row["content_json"])
        if row["content_json"]
        else {"version": 1, "blocks": []}
    )
    return {
        "schemaVersion": "aura.clinic-report-input.v1",
        "target": {
            "targetId": target_id,
            "userId": row["user_id"],
            "schoolId": row["school_id"],
            "schoolName": row["school_name"],
            "roundNumbers": rounds,
            "studentName": row["student_name"],
            "startTime": row["start_time"],
            "endTime": row["end_time"],
        },
        "scheduleMemo": row["description"] or "",
        "sourceNotes": row["source_notes"] or "",
        "questionChecks": checks,
        "editorDocument": document,
    }


def build_student_information(target_id: int) -> str:
    """이전 테스트 호출과의 호환용. 새 코드는 build_report_input을 사용한다."""
    return json.dumps(build_report_input(target_id), ensure_ascii=False, indent=2)


def normalize_report_input(value: dict[str, Any]) -> dict[str, Any]:
    """아우라 API 응답, 에디터 문서, 표준 입력을 한 형식으로 맞춘다."""
    if isinstance(value.get("editorDocument"), dict):
        normalized = dict(value)
        normalized.setdefault("schemaVersion", "aura.clinic-report-input.v1")
        normalized.setdefault("questionChecks", {})
        normalized.setdefault("sourceNotes", "")
        normalized.setdefault("scheduleMemo", "")
        normalized.setdefault("target", {})
        return normalized

    if isinstance(value.get("contentJson"), dict):
        return {
            "schemaVersion": "aura.clinic-report-input.v1",
            "target": {
                "targetId": value.get("targetId"),
                "schoolId": value.get("schoolId"),
                "schoolName": value.get("schoolName"),
                "roundNumbers": value.get("roundNumbers") or [],
                "studentName": value.get("studentName"),
                "startTime": value.get("startTime"),
                "endTime": value.get("endTime"),
            },
            "sourceNotes": value.get("sourceNotes") or "",
            "scheduleMemo": value.get("scheduleMemo") or "",
            "questionChecks": value.get("questionChecks") or {},
            "editorDocument": value["contentJson"],
            **({"options": value["options"]} if isinstance(value.get("options"), dict) else {}),
            **(
                {"scoreFormat": value["scoreFormat"]}
                if isinstance(value.get("scoreFormat"), dict)
                else {}
            ),
        }

    if isinstance(value.get("blocks"), list):
        return {
            "schemaVersion": "aura.clinic-report-input.v1",
            "target": {},
            "sourceNotes": "",
            "scheduleMemo": "",
            "questionChecks": {},
            "editorDocument": value,
        }
    raise ValueError(
        "아우라 JSON에 editorDocument, contentJson 또는 blocks가 필요합니다."
    )


def get_score_mode(report_input: dict[str, Any]) -> str:
    target = report_input.get("target") or {}
    user_id, school_id = target.get("userId"), target.get("schoolId")
    if not isinstance(user_id, int) or not isinstance(school_id, int):
        return "auto"
    with connect() as conn:
        row = conn.execute(
            """SELECT score_mode FROM clinic_report_generation_settings
               WHERE user_id = ? AND school_id = ?""",
            (user_id, school_id),
        ).fetchone()
    return str(row["score_mode"]) if row else "auto"


def set_score_mode(report_input: dict[str, Any], score_mode: str) -> None:
    if score_mode not in {"auto", "none"}:
        raise ValueError(f"지원하지 않는 평가 모드입니다: {score_mode}")
    target = report_input.get("target") or {}
    user_id, school_id = target.get("userId"), target.get("schoolId")
    if not isinstance(user_id, int) or not isinstance(school_id, int):
        return
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            """INSERT INTO clinic_report_generation_settings
               (user_id, school_id, score_mode, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, school_id) DO UPDATE SET
                 score_mode = excluded.score_mode,
                 updated_at = excluded.updated_at""",
            (user_id, school_id, score_mode, now, now),
        )
        conn.commit()


def get_active_score_format(report_input: dict[str, Any]) -> dict[str, Any] | None:
    supplied = report_input.get("scoreFormat")
    if isinstance(supplied, dict) and isinstance(supplied.get("items"), list):
        return {
            "id": supplied.get("id"),
            "name": str(supplied.get("name") or "입력 평가 양식"),
            "items": [str(item) for item in supplied["items"]],
            "source": "input",
        }
    school_id = (report_input.get("target") or {}).get("schoolId")
    if not isinstance(school_id, int):
        return None
    round_key = _round_key(report_input)
    with connect() as conn:
        row = conn.execute(
            """SELECT id, name, items_json, source
               FROM clinic_report_score_formats
               WHERE school_id = ? AND round_key = ? AND is_active = 1
               ORDER BY updated_at DESC, id DESC LIMIT 1""",
            (school_id, round_key),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "items": json.loads(row["items_json"]),
        "source": row["source"],
    }


def save_generated_score_format(
    report_input: dict[str, Any], name: str, items: list[str]
) -> int | None:
    target = report_input.get("target") or {}
    user_id, school_id = target.get("userId"), target.get("schoolId")
    clean_items = [str(item).strip() for item in items if str(item).strip()]
    if not isinstance(user_id, int) or not isinstance(school_id, int) or not clean_items:
        return None
    now = datetime.now(timezone.utc).isoformat()
    round_key = _round_key(report_input)
    with connect() as conn:
        conn.execute(
            """UPDATE clinic_report_score_formats SET is_active = 0
               WHERE school_id = ? AND round_key = ?""",
            (school_id, round_key),
        )
        cursor = conn.execute(
            """INSERT INTO clinic_report_score_formats
               (user_id, school_id, round_key, name, items_json, source,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'generated', ?, ?)""",
            (user_id, school_id, round_key, name.strip() or "기본 평가 양식",
             json.dumps(clean_items, ensure_ascii=False), now, now),
        )
        conn.commit()
        return int(cursor.lastrowid)


def _round_key(report_input: dict[str, Any]) -> str:
    rounds = (report_input.get("target") or {}).get("roundNumbers") or []
    return ",".join(str(number) for number in rounds)


def find_target_id(student_name: str, round_number: int) -> int:
    with connect() as conn:
        rows = conn.execute(
            """SELECT t.id, r.round_numbers_json, e.start_time
               FROM aura_round_targets t
               JOIN aura_clinic_rounds r ON r.id = t.round_id
               JOIN events e ON e.id = r.event_id
               WHERE t.student_name = ?
               ORDER BY e.start_time DESC""",
            (student_name,),
        ).fetchall()
    for row in rows:
        if round_number in json.loads(row["round_numbers_json"] or "[]"):
            return int(row["id"])
    raise ValueError(f"{student_name} 학생의 {round_number}회차 데이터를 찾을 수 없습니다.")


def recent_targets(limit: int = 30) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT t.id, t.student_name, s.name AS school_name,
                      r.round_numbers_json, e.start_time
               FROM aura_round_targets t
               JOIN aura_clinic_rounds r ON r.id = t.round_id
               JOIN aura_schools s ON s.id = r.school_id
               JOIN events e ON e.id = r.event_id
               ORDER BY e.start_time DESC, t.sort_order
               LIMIT ?""",
            (max(1, min(limit, 200)),),
        ).fetchall()
    return [dict(row) for row in rows]


def start_run(
    target_id: int | None,
    model: str,
    cache_mode: str,
    prompt_hash: str,
    *,
    input_json: dict[str, Any] | None = None,
    score_mode: str = "auto",
    score_format_id: int | None = None,
    provider: str = "gemini",
    input_hash: str | None = None,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO clinic_report_generation_runs
               (target_id, model, cache_mode, prompt_hash, status, created_at,
                input_json, score_mode, score_format_id, provider, input_hash)
               VALUES (?, ?, ?, ?, 'started', ?, ?, ?, ?, ?, ?)""",
            (target_id, model, cache_mode, prompt_hash, now,
             json.dumps(input_json, ensure_ascii=False) if input_json else None,
             score_mode, score_format_id, provider, input_hash),
        )
        conn.commit()
        return int(cursor.lastrowid)


def find_completed_run(
    target_id: int,
    model: str,
    input_hash: str,
    prompt_hash: str,
) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """SELECT id, provider, model, cache_mode, response_json, completed_at
               FROM clinic_report_generation_runs
               WHERE target_id = ? AND model = ? AND input_hash = ?
                 AND prompt_hash = ? AND status = 'completed'
                 AND response_json IS NOT NULL
               ORDER BY completed_at DESC, id DESC LIMIT 1""",
            (target_id, model, input_hash, prompt_hash),
        ).fetchone()
    if not row:
        return None
    return {
        "runId": row["id"],
        "provider": row["provider"],
        "model": row["model"],
        "cacheMode": row["cache_mode"],
        "output": json.loads(row["response_json"]),
        "completedAt": row["completed_at"],
    }


def list_completed_runs(target_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, provider, model, cache_mode, response_json, completed_at
               FROM clinic_report_generation_runs
               WHERE target_id = ? AND status = 'completed'
                 AND response_json IS NOT NULL
               ORDER BY completed_at DESC, id DESC""",
            (target_id,),
        ).fetchall()
    seen: set[str] = set()
    result = []
    for row in rows:
        if row["model"] in seen:
            continue
        seen.add(row["model"])
        result.append({
            "runId": row["id"],
            "provider": row["provider"],
            "model": row["model"],
            "cacheMode": row["cache_mode"],
            "output": json.loads(row["response_json"]),
            "completedAt": row["completed_at"],
            "reused": True,
        })
    return result


def finish_run(
    run_id: int,
    response_json: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    status = "failed" if error else "completed"
    with connect() as conn:
        conn.execute(
            """UPDATE clinic_report_generation_runs
               SET status = ?, response_text = ?, response_json = ?,
                   error_message = ?, completed_at = ?
               WHERE id = ?""",
            (status,
             json.dumps(response_json, ensure_ascii=False) if response_json else None,
             json.dumps(response_json, ensure_ascii=False) if response_json else None,
             error, now, run_id),
        )
        conn.commit()


def set_run_cache_mode(run_id: int, cache_mode: str) -> None:
    if cache_mode not in {"implicit", "explicit"}:
        raise ValueError(f"지원하지 않는 캐시 모드입니다: {cache_mode}")
    with connect() as conn:
        conn.execute(
            "UPDATE clinic_report_generation_runs SET cache_mode = ? WHERE id = ?",
            (cache_mode, run_id),
        )
        conn.commit()


def set_run_score_format(run_id: int, score_format_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE clinic_report_generation_runs SET score_format_id = ? WHERE id = ?",
            (score_format_id, run_id),
        )
        conn.commit()


def schema_summary() -> dict[str, Any]:
    with connect() as conn:
        return {
            table: [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
            for table in (
                "gemini_context_caches",
                "clinic_report_generation_runs",
                "clinic_report_score_formats",
                "clinic_report_generation_settings",
            )
        }
