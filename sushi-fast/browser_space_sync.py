"""Account-scoped URL snapshots for the Ego Lite Space sync extension.

Only the AI Office gateway calls this after authenticating a Sushi owner. This
module stores tab URLs and group labels; it never stores browser credentials.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

from auth import userdb


MAX_TABS = 250
MAX_BYTES = 500_000


def _schema(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS ai_office_browser_spaces (
        account_id INTEGER NOT NULL,
        space_name TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 0,
        tabs_json TEXT NOT NULL DEFAULT '[]',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(account_id, space_name)
    )""")


def _space(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        raise ValueError("스페이스 이름은 1~120자로 입력해 주세요.")
    return value.strip()


def _tabs(value: object) -> list[dict]:
    if not isinstance(value, list) or len(value) > MAX_TABS:
        raise ValueError("탭은 최대 250개까지 동기화할 수 있습니다.")
    result = []
    for tab in value:
        if not isinstance(tab, dict):
            raise ValueError("탭 형식이 올바르지 않습니다.")
        url = tab.get("url")
        group = tab.get("group", "")
        color = tab.get("color", "grey")
        if not isinstance(url, str) or len(url) > 4096:
            raise ValueError("탭 URL이 올바르지 않습니다.")
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("웹 주소만 동기화할 수 있습니다.")
        if not isinstance(group, str) or len(group) > 80:
            raise ValueError("탭 그룹 이름이 올바르지 않습니다.")
        if color not in {"grey", "blue", "red", "yellow", "green", "pink", "purple", "cyan", "orange"}:
            color = "grey"
        result.append({"url": url, "group": group, "color": color})
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        raise ValueError("동기화할 탭 목록이 너무 큽니다.")
    return result


def _read(db, account_id: int, space: str) -> dict:
    row = db.execute(
        "SELECT revision, tabs_json, updated_at FROM ai_office_browser_spaces "
        "WHERE account_id=? AND space_name=?", (account_id, space)
    ).fetchone()
    if row is None:
        return {"space": space, "revision": 0, "tabs": [], "updated_at": None}
    return {"space": space, "revision": row["revision"],
            "tabs": json.loads(row["tabs_json"]), "updated_at": row["updated_at"]}


async def handle(request: Request, account_id: int) -> JSONResponse:
    try:
        if request.method == "GET":
            space = _space(request.query_params.get("space"))
            with userdb.get_connection() as db:
                _schema(db)
                result = _read(db, account_id, space)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        if request.method != "PUT":
            return JSONResponse({"detail": "지원하지 않는 요청입니다."}, status_code=405)
        body = await request.body()
        if len(body) > MAX_BYTES + 4096:
            raise ValueError("동기화 요청이 너무 큽니다.")
        data = json.loads(body)
        space = _space(data.get("space"))
        base_revision = data.get("base_revision")
        if type(base_revision) is not int or base_revision < 0:
            raise ValueError("동기화 버전이 올바르지 않습니다.")
        tabs = _tabs(data.get("tabs"))
        with userdb.get_connection() as db:
            db.execute("BEGIN IMMEDIATE")
            _schema(db)
            current = _read(db, account_id, space)
            if current["revision"] != base_revision:
                return JSONResponse({"detail": "다른 기기의 변경이 먼저 저장됐습니다.", **current},
                                    status_code=409, headers={"Cache-Control": "no-store"})
            revision = base_revision + 1
            db.execute("""INSERT INTO ai_office_browser_spaces(account_id,space_name,revision,tabs_json)
                VALUES(?,?,?,?) ON CONFLICT(account_id,space_name) DO UPDATE SET
                revision=excluded.revision,tabs_json=excluded.tabs_json,updated_at=CURRENT_TIMESTAMP""",
                (account_id, space, revision, json.dumps(tabs, ensure_ascii=False, separators=(",", ":"))))
            db.commit()
            result = _read(db, account_id, space)
        return JSONResponse(result, headers={"Cache-Control": "no-store"})
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return JSONResponse({"detail": str(exc) or "요청을 확인해 주세요."}, status_code=400,
                            headers={"Cache-Control": "no-store"})
