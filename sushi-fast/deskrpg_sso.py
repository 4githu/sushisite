"""Sushi identity adapter for an unmodified, loopback-only DeskRPG server.

No upstream credentials or DeskRPG JWTs are sent to the browser. Cross-host
sign-in uses a single-use, hashed, 60-second ticket and the existing Sushi JWT.
"""
import asyncio
import base64
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time

import httpx
from auth import userdb

HOST = "desk.chobab.app"
UPSTREAM = "http://127.0.0.1:3102"
SOCKET_UPSTREAM = "http://127.0.0.1:3103"
SYSTEM_ID = "deskrpg-office"
_lock = asyncio.Lock()


def ensure_schema():
    with userdb.get_connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS deskrpg_identity (account_id INTEGER PRIMARY KEY, user_id TEXT UNIQUE NOT NULL, nickname TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS deskrpg_sso_tickets (digest TEXT PRIMARY KEY, account_id INTEGER NOT NULL, expires INTEGER NOT NULL)")
        db.commit()


def issue_ticket(account_id):
    ticket = secrets.token_urlsafe(32)
    with userdb.get_connection() as db:
        db.execute("DELETE FROM deskrpg_sso_tickets WHERE expires < ?", (int(time.time()),))
        db.execute("INSERT INTO deskrpg_sso_tickets VALUES (?, ?, ?)", (hashlib.sha256(ticket.encode()).hexdigest(), account_id, int(time.time()) + 60))
        db.commit()
    return ticket


def consume_ticket(ticket):
    if not ticket or len(ticket) > 100:
        return None
    with userdb.get_connection() as db:
        db.execute("BEGIN IMMEDIATE")
        digest = hashlib.sha256(ticket.encode()).hexdigest()
        row = db.execute("SELECT account_id, expires FROM deskrpg_sso_tickets WHERE digest=?", (digest,)).fetchone()
        db.execute("DELETE FROM deskrpg_sso_tickets WHERE digest=?", (digest,))
        db.commit()
    return int(row["account_id"]) if row and row["expires"] >= time.time() else None


def _secret():
    for line in (Path.home() / ".deskrpg/.env.local").read_text().splitlines():
        if line.startswith("JWT_SECRET="):
            return line.partition("=")[2].strip().strip("\"'").encode()
    raise RuntimeError("DeskRPG runtime secret missing")


def sign_identity(user_id, nickname):
    def enc(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")
    now = int(time.time())
    body = enc({"alg": "HS256"}) + b"." + enc({"userId": user_id, "nickname": nickname, "iat": now, "exp": now + 300})
    sig = base64.urlsafe_b64encode(hmac.new(_secret(), body, hashlib.sha256).digest()).rstrip(b"=")
    return (body + b"." + sig).decode()


async def upstream_cookie(account_id, role):
    async with _lock:
        with userdb.get_connection() as db:
            identity = db.execute("SELECT user_id, nickname FROM deskrpg_identity WHERE account_id=?", (account_id,)).fetchone()
        if identity is None:
            # Recover idempotently after an interrupted registration. DeskRPG
            # owns writes/migrations; this read is only for identity recovery.
            with sqlite3.connect(Path.home() / ".deskrpg/data/deskrpg.db") as db:
                recovered = db.execute("SELECT id,nickname FROM users WHERE login_id=?", (f"sushi-{account_id}",)).fetchone()
                count = db.execute("SELECT count(*) FROM users").fetchone()[0]
            if recovered:
                user_id, nickname = recovered
            else:
                if count == 0 and role != "owner":
                    raise PermissionError("The office owner must initialize DeskRPG first")
                nickname = f"Chobab {account_id}"
                async with httpx.AsyncClient(timeout=20) as client:
                    response = await client.post(UPSTREAM + "/api/auth/register", json={"loginId": f"sushi-{account_id}", "nickname": nickname, "password": secrets.token_urlsafe(48)})
                    response.raise_for_status()
                    user_id = response.json()["user"]["id"]
            with userdb.get_connection() as db:
                db.execute("INSERT INTO deskrpg_identity VALUES (?,?,?)", (account_id, user_id, nickname))
                db.commit()
        else:
            user_id, nickname = identity["user_id"], identity["nickname"]
    return "token=" + sign_identity(user_id, nickname)


def with_locale(cookie, request):
    # Only this non-credential preference may pass the identity boundary.
    locale = request.cookies.get("deskrpg-locale", "ko")
    if locale not in {"ko", "en", "ja", "zh"}:
        locale = "ko"
    return cookie + "; deskrpg-locale=" + locale
