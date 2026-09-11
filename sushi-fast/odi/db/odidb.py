# odi/db/odidb.py

import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = (BASE_DIR / "odi.db").resolve()
_REPORT_SCHEMA_READY: set[Path] = set()
SESSION_MEDIA_VERSION = "session-media-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_after_minutes(minutes: int) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(minutes=minutes)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def json_dumps(data: dict[str, Any] | list[Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def json_loads_or_none(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def bind_feedback_media(
    feedback: dict[str, Any],
    session_id: str,
) -> dict[str, Any]:
    """Return a copy with media explicitly bound to its owning ODI session.

    Legacy reports without ``media`` stay byte-shape compatible. Existing and
    unknown media keys are preserved so this can be rolled out incrementally.
    """
    bound = json.loads(json.dumps(feedback))
    media = bound.get("media")
    if not isinstance(media, dict):
        return bound

    media["version"] = SESSION_MEDIA_VERSION
    media["session_id"] = session_id
    return bound


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(schema_path: str | Path = "odi/db/schema.sql", db_path: Path = DB_PATH) -> None:
    schema = Path(schema_path).read_text(encoding="utf-8")

    with get_conn(db_path) as conn:
        conn.executescript(schema)


def ensure_report_schema(db_path: Path = DB_PATH) -> None:
    resolved = Path(db_path).resolve()
    if resolved in _REPORT_SCHEMA_READY:
        return
    init_db(schema_path=BASE_DIR / "schema.sql", db_path=resolved)
    _REPORT_SCHEMA_READY.add(resolved)


def validate_json_owner(data: dict[str, Any], owner_id: str) -> None:
    json_owner_id = data.get("owner_id")

    if json_owner_id is not None and str(json_owner_id) != str(owner_id):
        raise ValueError(f"JSON owner_id가 DB owner_id와 다릅니다. json={json_owner_id}, db={owner_id}")


def create_user(
    user_id: str,
    config: dict[str, Any],
    auth_id: str | None = None,
    recent_template: dict[str, Any] | None = None,
    db_path: Path = DB_PATH,
) -> None:
    validate_json_owner(config, user_id)

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, auth_id, recent_template, config)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                auth_id,
                json_dumps(recent_template) if recent_template is not None else None,
                json_dumps(config),
            ),
        )


def get_user(user_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT user_id, auth_id, recent_template, config, created_at, updated_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    config = json.loads(row["config"])
    comparison = get_user_report_comparison(str(row["user_id"]), db_path=db_path)
    account_average = comparison.get("account_average")
    if account_average:
        config.setdefault("dashboard", {})["average_score"] = account_average["overall_score"]
        config.setdefault("statistics", {})["session_count"] = account_average["session_count"]

    return {
        "user_id": row["user_id"],
        "auth_id": row["auth_id"],
        "recent_template": json_loads_or_none(row["recent_template"]),
        "config": config,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_user_by_auth_id(auth_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT user_id, auth_id, recent_template, config, created_at, updated_at
            FROM users
            WHERE auth_id = ?
            """,
            (auth_id,),
        ).fetchone()

    if row is None:
        return None

    config = json.loads(row["config"])
    comparison = get_user_report_comparison(str(row["user_id"]), db_path=db_path)
    account_average = comparison.get("account_average")
    if account_average:
        config.setdefault("dashboard", {})["average_score"] = account_average["overall_score"]
        config.setdefault("statistics", {})["session_count"] = account_average["session_count"]

    return {
        "user_id": row["user_id"],
        "auth_id": row["auth_id"],
        "recent_template": json_loads_or_none(row["recent_template"]),
        "config": config,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def update_user_config(
    user_id: str,
    config: dict[str, Any],
    db_path: Path = DB_PATH,
) -> None:
    validate_json_owner(config, user_id)

    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE users
            SET config = ?
            WHERE user_id = ?
            """,
            (json_dumps(config), user_id),
        )

        if cur.rowcount == 0:
            raise ValueError(f"존재하지 않는 user_id입니다: {user_id}")


def update_recent_template(
    user_id: str,
    template: dict[str, Any] | None,
    db_path: Path = DB_PATH,
) -> None:
    if template is not None:
        validate_json_owner(template, user_id)

    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE users
            SET recent_template = ?
            WHERE user_id = ?
            """,
            (json_dumps(template) if template is not None else None, user_id),
        )

        if cur.rowcount == 0:
            raise ValueError(f"존재하지 않는 user_id입니다: {user_id}")


def create_template(
    owner_id: str,
    template: dict[str, Any],
    template_id: str | None = None,
    db_path: Path = DB_PATH,
) -> str:
    validate_json_owner(template, owner_id)

    # snapshot은 항상 새로운 template_id를 갖는다.
    if template_id is None:
        template_id = make_id("template")

    template = json.loads(json.dumps(template))

    template["id"] = template_id
    template["template_id"] = template_id
    template["owner_id"] = owner_id

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO templates (template_id, owner_id, template)
            VALUES (?, ?, ?)
            """,
            (
                template_id,
                owner_id,
                json_dumps(template),
            ),
        )

    return template_id


def get_template(template_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT template_id, owner_id, template, created_at, updated_at
            FROM templates
            WHERE template_id = ?
            """,
            (template_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "template_id": row["template_id"],
        "owner_id": row["owner_id"],
        "template": json.loads(row["template"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_templates_by_owner(owner_id: str, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT template_id, owner_id, template, created_at, updated_at
            FROM templates
            WHERE owner_id = ?
            ORDER BY updated_at DESC
            """,
            (owner_id,),
        ).fetchall()

    return [
        {
            "template_id": row["template_id"],
            "owner_id": row["owner_id"],
            "template": json.loads(row["template"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def update_template(
    template_id: str,
    template: dict[str, Any],
    db_path: Path = DB_PATH,
) -> None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT owner_id
            FROM templates
            WHERE template_id = ?
            """,
            (template_id,),
        ).fetchone()

        if row is None:
            raise ValueError(f"존재하지 않는 template_id입니다: {template_id}")

        validate_json_owner(template, row["owner_id"])

        template["id"] = template_id
        template["owner_id"] = row["owner_id"]

        conn.execute(
            """
            UPDATE templates
            SET template = ?
            WHERE template_id = ?
            """,
            (json_dumps(template), template_id),
        )


def delete_template(template_id: str, db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            DELETE FROM templates
            WHERE template_id = ?
            """,
            (template_id,),
        )


def clone_recent_template_to_template(
    user_id: str,
    db_path: Path = DB_PATH,
) -> str:
    user = get_user(user_id, db_path=db_path)

    if user is None:
        raise ValueError(f"존재하지 않는 user_id입니다: {user_id}")

    recent_template = user.get("recent_template")

    if recent_template is None:
        raise ValueError("recent_template이 없습니다.")

    new_template_id = make_id("template")
    recent_template["id"] = new_template_id
    recent_template["owner_id"] = user_id

    template_id = create_template(
        owner_id=user_id,
        template=recent_template,
        template_id=new_template_id,
        db_path=db_path,
    )

    saved_template = get_template(template_id, db_path=db_path)

    if saved_template is None:
        raise ValueError("템플릿 저장 후 조회에 실패했습니다.")

    update_recent_template(
        user_id=user_id,
        template=saved_template["template"],
        db_path=db_path,
    )

    return template_id


def generate_unique_pin(db_path: Path = DB_PATH) -> str:
    with get_conn(db_path) as conn:
        for _ in range(100):
            pin_code = f"{random.randint(0, 9999):04d}"
            row = conn.execute(
                """
                SELECT pin_code
                FROM pre_sessions
                WHERE pin_code = ?
                """,
                (pin_code,),
            ).fetchone()

            if row is None:
                return pin_code

    raise RuntimeError("사용 가능한 4자리 핀번호를 생성하지 못했습니다.")


def create_pre_session(
    template_id: str,
    expires_minutes: int = 30,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    pin_code = generate_unique_pin(db_path=db_path)
    expires_at = utc_after_minutes(expires_minutes)

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO pre_sessions (pin_code, template_id, state, expires_at)
            VALUES (?, ?, 'waiting', ?)
            """,
            (pin_code, template_id, expires_at),
        )

    pre_session = get_pre_session_by_pin(pin_code, db_path=db_path)

    if pre_session is None:
        raise ValueError("pre_session 생성 후 조회에 실패했습니다.")

    return pre_session


def get_pre_session_by_pin(pin_code: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT pin_code, template_id, session_id, state, expires_at, created_at
            FROM pre_sessions
            WHERE pin_code = ?
            """,
            (pin_code,),
        ).fetchone()

    if row is None:
        return None

    report_job = get_report_job_by_pre_session_pin(pin_code, db_path=db_path)
    return {
        "pin_code": row["pin_code"],
        "template_id": row["template_id"],
        "session_id": row["session_id"],
        "state": row["state"],
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
        "report_status": report_job["status"] if report_job else "not_started",
        "report_error": report_job.get("error_code") if report_job else None,
    }


def update_pre_session_state(
    pin_code: str,
    state: str,
    db_path: Path = DB_PATH,
) -> None:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE pre_sessions
            SET state = ?
            WHERE pin_code = ?
            """,
            (state, pin_code),
        )

        if cur.rowcount == 0:
            raise ValueError(f"존재하지 않는 pin_code입니다: {pin_code}")


def claim_pre_session(pin_code: str, db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE pre_sessions
            SET state = 'running'
            WHERE pin_code = ? AND state = 'waiting' AND session_id IS NULL AND expires_at > ?
            """,
            (pin_code, utc_now()),
        )
        if cur.rowcount != 1:
            raise ValueError("pre-session is not available")


def release_pre_session_claim(pin_code: str, db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE pre_sessions SET state = 'waiting' WHERE pin_code = ? AND state = 'running' AND session_id IS NULL",
            (pin_code,),
        )


def finish_linked_pre_session(
    *,
    pin_code: str,
    user_id: str,
    template_id: str,
    feedback: dict[str, Any],
    evc_session_id: str | None = None,
    report_request_id: str | None = None,
    db_path: Path = DB_PATH,
) -> str:
    ensure_report_schema(db_path)
    session_id = make_id("session")
    feedback = bind_feedback_media(feedback, session_id)
    now = utc_now()
    with get_conn(db_path) as conn:
        pre_session = conn.execute(
            "SELECT template_id, session_id, state FROM pre_sessions WHERE pin_code = ?",
            (pin_code,),
        ).fetchone()
        if pre_session is None:
            raise ValueError("pre-session does not exist")
        if pre_session["template_id"] != template_id:
            raise ValueError("pre-session template does not match EVC session")
        if pre_session["session_id"] is not None:
            return str(pre_session["session_id"])
        if pre_session["state"] != "running":
            raise ValueError("pre-session is not running")
        template = conn.execute(
            "SELECT owner_id, template FROM templates WHERE template_id = ?",
            (template_id,),
        ).fetchone()
        if template is None or str(template["owner_id"]) != str(user_id):
            raise ValueError("template owner does not match EVC session")
        conn.execute(
            """
            INSERT INTO sessions (
                session_id, user_id, template_id, template, feedback, state, started_at, ended_at
            ) VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)
            """,
            (session_id, user_id, template_id, template["template"], json_dumps(feedback), now, now),
        )
        updated = conn.execute(
            """
            UPDATE pre_sessions SET session_id = ?, state = 'finished'
            WHERE pin_code = ? AND state = 'running' AND session_id IS NULL
            """,
            (session_id, pin_code),
        )
        if updated.rowcount != 1:
            raise ValueError("pre-session changed while report was being stored")
        if evc_session_id:
            conn.execute(
                """
                INSERT INTO presentation_reports (
                    report_id, evc_session_id, odi_session_id, version, feedback_json,
                    generator, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evc_session_id) DO UPDATE SET
                    odi_session_id = excluded.odi_session_id,
                    version = excluded.version,
                    feedback_json = excluded.feedback_json,
                    generator = excluded.generator,
                    generated_at = excluded.generated_at
                """,
                (
                    make_id("report"), evc_session_id, session_id,
                    str(feedback.get("version", "presentation-report-v1")),
                    json_dumps(feedback),
                    str((feedback.get("generation") or {}).get("generator", "unknown")),
                    str((feedback.get("generation") or {}).get("generated_at", now)),
                ),
            )
        if report_request_id:
            conn.execute(
                """
                UPDATE presentation_report_jobs
                SET status = 'ready', odi_session_id = ?, finished_at = ?, error_code = NULL
                WHERE request_id = ?
                """,
                (session_id, now, report_request_id),
            )
    return session_id


def upsert_presentation_segment(
    *,
    evc_session_id: str,
    step: int,
    segment: dict[str, Any],
    owner_user_id: str | None = None,
    pre_session_pin: str | None = None,
    expires_at: str | None = None,
    db_path: Path = DB_PATH,
) -> None:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO presentation_segments (
                evc_session_id, step, owner_user_id, pre_session_pin, segment_json, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(evc_session_id, step) DO UPDATE SET
                segment_json = excluded.segment_json,
                expires_at = excluded.expires_at
            """,
            (evc_session_id, step, owner_user_id, pre_session_pin, json_dumps(segment), expires_at),
        )


def list_presentation_segments(evc_session_id: str, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT segment_json FROM presentation_segments WHERE evc_session_id = ? ORDER BY step",
            (evc_session_id,),
        ).fetchall()
    return [json.loads(row["segment_json"]) for row in rows]


def upsert_presentation_reaction(
    *,
    evc_session_id: str,
    sequence: int,
    reaction: dict[str, Any],
    owner_user_id: str | None = None,
    pre_session_pin: str | None = None,
    expires_at: str | None = None,
    db_path: Path = DB_PATH,
) -> None:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO presentation_reactions (
                evc_session_id, sequence, owner_user_id, pre_session_pin, reaction_json, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(evc_session_id, sequence) DO UPDATE SET
                reaction_json = excluded.reaction_json,
                expires_at = excluded.expires_at
            """,
            (
                evc_session_id,
                sequence,
                owner_user_id,
                pre_session_pin,
                json_dumps(reaction),
                expires_at,
            ),
        )


def list_presentation_reactions(
    evc_session_id: str, db_path: Path = DB_PATH
) -> list[dict[str, Any]]:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT reaction_json FROM presentation_reactions WHERE evc_session_id = ? ORDER BY sequence",
            (evc_session_id,),
        ).fetchall()
    return [json.loads(row["reaction_json"]) for row in rows]


def get_evc_session_id_by_pre_session_pin(
    pin_code: str, db_path: Path = DB_PATH
) -> str | None:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT evc_session_id FROM presentation_segments
            WHERE pre_session_pin = ? ORDER BY step DESC LIMIT 1
            """,
            (pin_code,),
        ).fetchone()
    return str(row["evc_session_id"]) if row else None


def start_report_job(
    *, evc_session_id: str, request_id: str, db_path: Path = DB_PATH
) -> dict[str, Any]:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM presentation_report_jobs WHERE request_id = ?", (request_id,)
        ).fetchone()
        if existing is None:
            job_id = make_id("report_job")
            conn.execute(
                """
                INSERT INTO presentation_report_jobs (
                    job_id, evc_session_id, request_id, status, attempt_count, started_at
                ) VALUES (?, ?, ?, 'generating', 1, ?)
                """,
                (job_id, evc_session_id, request_id, utc_now()),
            )
        else:
            job_id = existing["job_id"]
            if existing["status"] == "failed":
                conn.execute(
                    """
                    UPDATE presentation_report_jobs SET status = 'generating',
                        attempt_count = attempt_count + 1, error_code = NULL, started_at = ?
                    WHERE job_id = ?
                    """,
                    (utc_now(), job_id),
                )
    return get_report_job(request_id=request_id, db_path=db_path) or {}


def fail_report_job(request_id: str, error_code: str, db_path: Path = DB_PATH) -> None:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            UPDATE presentation_report_jobs
            SET status = 'failed', error_code = ?, finished_at = ?
            WHERE request_id = ?
            """,
            (error_code, utc_now(), request_id),
        )


def get_report_job(request_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM presentation_report_jobs WHERE request_id = ?", (request_id,)
        ).fetchone()
    return dict(row) if row else None


def get_presentation_report(evc_session_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM presentation_reports WHERE evc_session_id = ?", (evc_session_id,)
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["feedback"] = json.loads(result.pop("feedback_json"))
    return result


def get_presentation_transcript_for_session(
    session_id: str, user_id: str, db_path: Path = DB_PATH
) -> list[dict[str, Any]]:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        owned = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if owned is None:
            raise ValueError("session does not exist or is not owned by the user")
        report = conn.execute(
            "SELECT evc_session_id FROM presentation_reports WHERE odi_session_id = ?",
            (session_id,),
        ).fetchone()
    if report is None:
        return []
    return list_presentation_segments(str(report["evc_session_id"]), db_path=db_path)


def delete_presentation_source_data(
    session_id: str, user_id: str, db_path: Path = DB_PATH
) -> int:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        owned = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if owned is None:
            raise ValueError("session does not exist or is not owned by the user")
        report = conn.execute(
            "SELECT evc_session_id FROM presentation_reports WHERE odi_session_id = ?",
            (session_id,),
        ).fetchone()
        if report is None:
            return 0
        evc_session_id = str(report["evc_session_id"])
        deleted_segments = conn.execute(
            "DELETE FROM presentation_segments WHERE evc_session_id = ?", (evc_session_id,)
        ).rowcount
        deleted_reactions = conn.execute(
            "DELETE FROM presentation_reactions WHERE evc_session_id = ?", (evc_session_id,)
        ).rowcount
    return deleted_segments + deleted_reactions


def get_report_job_by_pre_session_pin(
    pin_code: str, db_path: Path = DB_PATH
) -> dict[str, Any] | None:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT j.* FROM presentation_report_jobs j
            WHERE j.evc_session_id = (
                SELECT evc_session_id FROM presentation_segments
                WHERE pre_session_pin = ? ORDER BY step DESC LIMIT 1
            )
            ORDER BY j.created_at DESC LIMIT 1
            """,
            (pin_code,),
        ).fetchone()
    return dict(row) if row else None


def recover_stale_report_jobs(stale_minutes: int = 10, db_path: Path = DB_PATH) -> int:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE presentation_report_jobs
            SET status = 'queued', error_code = 'worker_interrupted'
            WHERE status = 'generating' AND started_at <= datetime('now', ?)
            """,
            (f"-{max(1, stale_minutes)} minutes",),
        )
    return cur.rowcount


def delete_expired_presentation_data(db_path: Path = DB_PATH) -> dict[str, int]:
    ensure_report_schema(db_path)
    now = utc_now()
    with get_conn(db_path) as conn:
        segment_count = conn.execute(
            "DELETE FROM presentation_segments WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,)
        ).rowcount
        reaction_count = conn.execute(
            "DELETE FROM presentation_reactions WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,)
        ).rowcount
        report_count = conn.execute(
            "DELETE FROM presentation_reports WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,)
        ).rowcount
    return {"segments": segment_count, "reactions": reaction_count, "reports": report_count}


def attach_session_to_pre_session(
    pin_code: str,
    session_id: str,
    state: str = "finished",
    db_path: Path = DB_PATH,
) -> None:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE pre_sessions
            SET session_id = ?,
                state = ?
            WHERE pin_code = ?
            """,
            (session_id, state, pin_code),
        )

        if cur.rowcount == 0:
            raise ValueError(f"존재하지 않는 pin_code입니다: {pin_code}")


def delete_expired_pre_sessions(db_path: Path = DB_PATH) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            DELETE FROM pre_sessions
            WHERE expires_at <= ?
            """,
            (utc_now(),),
        )

    return cur.rowcount


def start_session_from_template(
    user_id: str,
    template_id: str,
    db_path: Path = DB_PATH,
) -> str:
    session_id = make_id("session")

    with get_conn(db_path) as conn:
        template_row = conn.execute(
            """
            SELECT template
            FROM templates
            WHERE template_id = ?
            """,
            (template_id,),
        ).fetchone()

        if template_row is None:
            raise ValueError(f"존재하지 않는 template_id입니다: {template_id}")

        conn.execute(
            """
            INSERT INTO sessions (
                session_id,
                user_id,
                template_id,
                template,
                feedback,
                state,
                started_at
            )
            VALUES (?, ?, ?, ?, NULL, 'running', ?)
            """,
            (
                session_id,
                user_id,
                template_id,
                template_row["template"],
                utc_now(),
            ),
        )

    return session_id


def create_session_with_snapshot(
    user_id: str,
    template: dict[str, Any],
    feedback: dict[str, Any] | None = None,
    template_id: str | None = None,
    state: str = "completed",
    db_path: Path = DB_PATH,
) -> str:
    session_id = make_id("session")
    now = utc_now()
    if feedback is not None:
        feedback = bind_feedback_media(feedback, session_id)

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                session_id,
                user_id,
                template_id,
                template,
                feedback,
                state,
                started_at,
                ended_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                template_id,
                json_dumps(template),
                json_dumps(feedback) if feedback is not None else None,
                state,
                now,
                now if state == "completed" else None,
            ),
        )

    return session_id


def finish_session(
    session_id: str,
    feedback: dict[str, Any],
    db_path: Path = DB_PATH,
) -> None:
    feedback = bind_feedback_media(feedback, session_id)
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE sessions
            SET feedback = ?,
                state = 'completed',
                ended_at = ?
            WHERE session_id = ?
            """,
            (json_dumps(feedback), utc_now(), session_id),
        )

        if cur.rowcount == 0:
            raise ValueError(f"존재하지 않는 session_id입니다: {session_id}")


def update_session_media(
    session_id: str,
    user_id: str,
    media: dict[str, Any],
    db_path: Path = DB_PATH,
) -> None:
    """Attach playback media to one completed/running session without replacing its report."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT user_id, feedback FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None or str(row["user_id"]) != str(user_id):
            raise ValueError("영상 연결 대상 세션이 없거나 접근 권한이 없습니다.")

        feedback = json_loads_or_none(row["feedback"])
        if not isinstance(feedback, dict):
            feedback = {}

        existing_media = feedback.get("media")
        merged_media = dict(existing_media) if isinstance(existing_media, dict) else {}
        # session_id/version은 클라이언트 입력을 신뢰하지 않고 서버가 확정합니다.
        merged_media.update(media)
        feedback["media"] = merged_media
        feedback = bind_feedback_media(feedback, session_id)

        conn.execute(
            "UPDATE sessions SET feedback = ? WHERE session_id = ?",
            (json_dumps(feedback), session_id),
        )


def get_session(session_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT session_id, user_id, template_id, template, feedback, state, started_at, ended_at, created_at, updated_at
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "template_id": row["template_id"],
        "template": json.loads(row["template"]),
        "feedback": json_loads_or_none(row["feedback"]),
        "state": row["state"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_user_report_comparison(
    user_id: str,
    current_session_id: str | None = None,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """Build mutable account comparison data without copying it into feedback JSON."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT session_id, feedback, created_at
            FROM sessions
            WHERE user_id = ? AND state = 'completed' AND feedback IS NOT NULL
            ORDER BY created_at DESC, session_id DESC
            """,
            (user_id,),
        ).fetchall()

    scored: list[dict[str, Any]] = []
    for row in rows:
        feedback = json_loads_or_none(row["feedback"])
        if not isinstance(feedback, dict):
            continue
        score = feedback.get("score") or {}
        scores = (feedback.get("score_card") or {}).get("scores") or {}
        try:
            scored.append({
                "session_id": str(row["session_id"]),
                "overall_score": int(score["overall_score"]),
                "engagement": int(scores["engagement"]),
                "clarity": int(scores["clarity"]),
                "credibility": int(scores["credibility"]),
            })
        except (KeyError, TypeError, ValueError):
            continue

    account_average = None
    if scored:
        count = len(scored)
        account_average = {
            "overall_score": round(sum(item["overall_score"] for item in scored) / count),
            "engagement": round(sum(item["engagement"] for item in scored) / count),
            "clarity": round(sum(item["clarity"] for item in scored) / count),
            "credibility": round(sum(item["credibility"] for item in scored) / count),
            "session_count": count,
        }

    previous_session = None
    if current_session_id:
        current_index = next(
            (index for index, item in enumerate(scored) if item["session_id"] == current_session_id),
            None,
        )
        if current_index is not None and current_index + 1 < len(scored):
            current = scored[current_index]
            previous = scored[current_index + 1]
            previous_session = {
                "session_id": previous["session_id"],
                "overall_score": previous["overall_score"],
                "score_delta": current["overall_score"] - previous["overall_score"],
            }

    return {
        "account_average": account_average,
        "previous_session": previous_session,
    }


def get_latest_completed_session_by_template_id(
    template_id: str,
    db_path: Path = DB_PATH,
) -> dict[str, Any] | None:
    """Return a stable completed report used for a public product demo."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT session_id, user_id, template_id, template, feedback, state, started_at, ended_at, created_at, updated_at
            FROM sessions
            WHERE template_id = ? AND state = 'completed' AND feedback IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (template_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "template_id": row["template_id"],
        "template": json.loads(row["template"]),
        "feedback": json_loads_or_none(row["feedback"]),
        "state": row["state"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_sessions_by_user(
    user_id: str,
    limit: int = 20,
    db_path: Path = DB_PATH,
) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT session_id, user_id, template_id, template, feedback, state, started_at, ended_at, created_at, updated_at
            FROM sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    return [
        {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "template_id": row["template_id"],
            "template": json.loads(row["template"]),
            "feedback": json_loads_or_none(row["feedback"]),
            "state": row["state"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def delete_session(session_id: str, user_id: str | None = None, db_path: Path = DB_PATH) -> None:
    ensure_report_schema(db_path)
    with get_conn(db_path) as conn:
        owner_filter = "" if user_id is None else " AND user_id = ?"
        params = (session_id,) if user_id is None else (session_id, user_id)
        owned = conn.execute(
            f"SELECT session_id FROM sessions WHERE session_id = ?{owner_filter}", params
        ).fetchone()
        if owned is None:
            raise ValueError("삭제할 세션이 없거나 접근 권한이 없습니다.")
        evc_rows = conn.execute(
            "SELECT evc_session_id FROM presentation_reports WHERE odi_session_id = ?",
            (session_id,),
        ).fetchall()
        for row in evc_rows:
            evc_session_id = row["evc_session_id"]
            conn.execute("DELETE FROM presentation_segments WHERE evc_session_id = ?", (evc_session_id,))
            conn.execute("DELETE FROM presentation_reactions WHERE evc_session_id = ?", (evc_session_id,))
            conn.execute("DELETE FROM presentation_report_jobs WHERE evc_session_id = ?", (evc_session_id,))
            conn.execute("DELETE FROM presentation_reports WHERE evc_session_id = ?", (evc_session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def delete_expired_unlinked_templates(
    owner_id: str,
    favorite_template_ids: list[str],
    max_age_minutes: int = 60,
    db_path: Path = DB_PATH,
) -> list[str]:
    """Remove old template snapshots that were never turned into a session.

    Completed reports always hold their own template snapshot in ``sessions``.
    Therefore a template that is neither favourited nor referenced by a session
    is safe to expire after the short grace period.
    """
    safe_minutes = max(1, min(max_age_minutes, 24 * 60))
    with get_conn(db_path) as conn:
        placeholders = ",".join("?" for _ in favorite_template_ids)
        excluded = f" AND t.template_id NOT IN ({placeholders})" if placeholders else ""
        rows = conn.execute(
            f"""
            SELECT t.template_id
            FROM templates t
            WHERE t.owner_id = ?
              AND t.created_at <= datetime('now', ?)
              AND NOT EXISTS (
                SELECT 1 FROM sessions s WHERE s.template_id = t.template_id
              )
              {excluded}
            """,
            [owner_id, f"-{safe_minutes} minutes", *favorite_template_ids],
        ).fetchall()
        template_ids = [row["template_id"] for row in rows]
        if template_ids:
            delete_placeholders = ",".join("?" for _ in template_ids)
            conn.execute(
                f"DELETE FROM templates WHERE template_id IN ({delete_placeholders})",
                template_ids,
            )
    return template_ids
