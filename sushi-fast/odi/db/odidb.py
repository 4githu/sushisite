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


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(schema_path: str | Path = "odi/db/schema.sql", db_path: Path = DB_PATH) -> None:
    schema = Path(schema_path).read_text(encoding="utf-8")

    with get_conn(db_path) as conn:
        conn.executescript(schema)


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

    return {
        "user_id": row["user_id"],
        "auth_id": row["auth_id"],
        "recent_template": json_loads_or_none(row["recent_template"]),
        "config": json.loads(row["config"]),
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

    return {
        "user_id": row["user_id"],
        "auth_id": row["auth_id"],
        "recent_template": json_loads_or_none(row["recent_template"]),
        "config": json.loads(row["config"]),
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

    return {
        "pin_code": row["pin_code"],
        "template_id": row["template_id"],
        "session_id": row["session_id"],
        "state": row["state"],
        "expires_at": row["expires_at"],
        "created_at": row["created_at"],
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


def delete_session(session_id: str, db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            DELETE FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        )