"""Synthetic account profile and verification HTTP contract; no real mail or users."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import JMT, router, sushihash, userdb


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(userdb, "DB_PATH", tmp_path / "accounts.db")
    monkeypatch.setattr(JMT, "SECRET_KEY", "synthetic-only-secret")
    monkeypatch.setattr(JMT, "ALGORITHM", "HS256")
    with sqlite3.connect(userdb.DB_PATH) as db:
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, name TEXT, created_at INTEGER, email_verified INTEGER)")
    userdb.create_user("one@example.invalid", sushihash.make_hash("Password1!"), "One", 1, email_verified=1)
    userdb.create_user("two@example.invalid", sushihash.make_hash("Password2!"), "Two", 1, email_verified=0)
    app = FastAPI()
    app.include_router(router.router)
    return TestClient(app), userdb.get_user("one@example.invalid")["id"], userdb.get_user("two@example.invalid")["id"]


def login(client, email="one@example.invalid", password="Password1!"):
    assert client.post("/auth/login", json={"email": email, "password": password}).json()["success"]
    return client.cookies.get("mainauth")


def test_name_change_returns_db_profile_and_fresh_cookie(accounts):
    client, first, _ = accounts
    old = login(client)
    response = client.put("/auth/user", json={"id": first, "name": "New Name"})
    profile = {"id": first, "email": "one@example.invalid", "name": "New Name", "email_verified": True}
    assert response.json() == {"success": True, "message": None, "data": profile, "email_verification_required": False}
    assert client.cookies.get("mainauth") != old
    assert JMT.jwt.decode(client.cookies.get("mainauth"), JMT.SECRET_KEY, algorithms=[JMT.ALGORITHM])["data"]["name"] == "New Name"
    assert client.get("/auth/isjwt", params={"key": "mainauth"}).json()["data"] == profile


def test_email_change_and_old_session_refresh_from_database(accounts):
    client, first, _ = accounts
    old = login(client)
    assert client.put("/auth/user", json={"id": first, "email": "new@example.invalid", "password": "bad"}).status_code == 403
    assert client.cookies.get("mainauth") == old
    result = client.put("/auth/user", json={"id": first, "email": "new@example.invalid", "password": "Password1!"})
    assert result.json()["email_verification_required"] is True
    assert result.json()["data"] == {"id": first, "email": "new@example.invalid", "name": "One", "email_verified": False}
    assert client.cookies.get("mainauth") != old
    client.cookies.clear()
    client.cookies.set("mainauth", old, domain="testserver.local")
    refreshed = client.get("/auth/isjwt", params={"key": "mainauth"})
    assert refreshed.json()["data"] == result.json()["data"]
    assert client.cookies.get("mainauth") != old


def test_send_and_confirm_current_email_once(accounts, monkeypatch):
    from auth import email_verified
    client, first, second = accounts
    sent = []
    monkeypatch.setattr(email_verified, "send_account_verification_email", lambda email, name, code: sent.append((email, code)))
    assert client.post("/auth/user/email-verification/send").status_code == 401
    login(client, "two@example.invalid", "Password2!")
    assert client.post("/auth/user/email-verification/send", json={"id": first, "email": "one@example.invalid"}).status_code == 422
    assert client.post("/auth/user/email-verification/send").json() == {"success": True}
    assert sent[0][0] == "two@example.invalid"
    code = sent[0][1]
    assert client.post("/auth/user/email-verification/send").status_code == 429
    wrong = client.post("/auth/user/email-verification/confirm", json={"code": "000000"})
    assert wrong.status_code == 400
    assert userdb.get_user(user_id=second)["email_verified"] == 0
    confirmed = client.post("/auth/user/email-verification/confirm", json={"code": code})
    assert confirmed.json() == {"success": True, "data": {"id": second, "email": "two@example.invalid", "name": "Two", "email_verified": True}, "email_verification_required": False}
    assert client.get("/auth/isjwt", params={"key": "mainauth"}).json()["data"]["email_verified"] is True
    assert client.post("/auth/user/email-verification/confirm", json={"code": code}).status_code == 400


def test_old_address_code_fails_after_email_changes_even_if_restored(accounts, monkeypatch):
    from auth import email_verified
    client, first, _ = accounts
    sent = []
    monkeypatch.setattr(email_verified, "send_account_verification_email", lambda email, name, code: sent.append(code))
    login(client)
    client.put("/auth/user", json={"id": first, "email": "new@example.invalid", "password": "Password1!"})
    assert client.post("/auth/user/email-verification/send").status_code == 200
    code = sent[-1]
    client.put("/auth/user", json={"id": first, "email": "one@example.invalid", "password": "Password1!"})
    assert client.post("/auth/user/email-verification/confirm", json={"code": code}).status_code == 400
    assert userdb.get_user(user_id=first)["email_verified"] == 0


def test_expiry_attempt_limit_and_resend(accounts, monkeypatch):
    from auth import email_verified, service
    client, _, _ = accounts
    sent = []
    now = [10000]
    monkeypatch.setattr(service.time, "time", lambda: now[0])
    monkeypatch.setattr(email_verified, "send_account_verification_email", lambda email, name, code: sent.append(code))
    login(client, "two@example.invalid", "Password2!")
    client.post("/auth/user/email-verification/send")
    now[0] += 61
    client.post("/auth/user/email-verification/send")
    assert len(sent) == 2
    assert client.post("/auth/user/email-verification/confirm", json={"code": sent[0]}).status_code == 400
    now[0] += 3601
    assert client.post("/auth/user/email-verification/confirm", json={"code": sent[1]}).status_code == 400
    now[0] += 1
    client.post("/auth/user/email-verification/send")
    for _ in range(5):
        assert client.post("/auth/user/email-verification/confirm", json={"code": "000000"}).status_code == 400
    assert client.post("/auth/user/email-verification/confirm", json={"code": sent[-1]}).status_code == 400


def test_send_daily_limit_applies_after_cooldown(accounts, monkeypatch):
    from auth import email_verified, service
    client, _, _ = accounts
    login(client, "two@example.invalid", "Password2!")
    now = [10000]
    monkeypatch.setattr(service.time, "time", lambda: now[0])
    sent = []
    monkeypatch.setattr(email_verified, "send_account_verification_email", lambda email, name, code: sent.append(email))
    for _ in range(5):
        assert client.post("/auth/user/email-verification/send").status_code == 200
        now[0] += 61
    assert client.post("/auth/user/email-verification/send").status_code == 429
    assert len(sent) == 5
    now[0] += 86400
    assert client.post("/auth/user/email-verification/send").status_code == 200


def test_delivery_failure_and_deleted_account(accounts, monkeypatch, caplog):
    from auth import email_verified
    client, first, second = accounts
    def failed_delivery(email, name, code):
        raise RuntimeError("transport unavailable")
    monkeypatch.setattr(email_verified, "send_account_verification_email", failed_delivery)
    login(client, "two@example.invalid", "Password2!")
    token = client.cookies.get("mainauth")
    assert client.post("/auth/user/email-verification/send").status_code == 503
    assert client.cookies.get("mainauth") == token
    assert userdb.get_user(user_id=second)["email_verified"] == 0
    assert client.post("/auth/user/email-verification/confirm", json={"code": "123456"}).status_code == 400
    assert "123456" not in caplog.text
    userdb.delete_user(second)
    assert client.post("/auth/user/email-verification/send").status_code == 401
    assert client.post("/auth/user/email-verification/confirm", json={"code": "123456"}).status_code == 401
    assert client.get("/auth/isjwt", params={"key": "mainauth"}).status_code == 401


def test_other_account_and_invalid_cookie_cannot_verify(accounts, monkeypatch):
    from auth import email_verified
    client, first, second = accounts
    sent = []
    monkeypatch.setattr(email_verified, "send_account_verification_email", lambda email, name, code: sent.append((email, code)))
    login(client, "two@example.invalid", "Password2!")
    client.post("/auth/user/email-verification/send")
    login(client)
    assert client.post("/auth/user/email-verification/confirm", json={"code": sent[-1][1]}).status_code == 400
    assert userdb.get_user(user_id=second)["email_verified"] == 0
    client.cookies.clear()
    assert client.post("/auth/user/email-verification/confirm", json={"code": sent[-1][1]}).status_code == 401
    client.cookies.set("mainauth", "forged", domain="testserver.local")
    assert client.post("/auth/user/email-verification/send").status_code == 401


def test_send_never_targets_new_email_with_old_email_code(accounts, monkeypatch):
    from auth import email_verified, userdb as db
    client, first, _ = accounts
    login(client)
    client.put("/auth/user", json={"id": first, "email": "new@example.invalid", "password": "Password1!"})
    original = db.reserve_email_verification
    def change_before_reservation(user_id, email, digest, now):
        db.edit_user(first, "later@example.invalid", db.get_user(user_id=first)["password_hash"], "One", 0)
        return original(user_id, email, digest, now)
    monkeypatch.setattr(db, "reserve_email_verification", change_before_reservation)
    sent = []
    monkeypatch.setattr(email_verified, "send_account_verification_email", lambda email, name, code: sent.append(email))
    assert client.post("/auth/user/email-verification/send").status_code == 409
    assert not sent


def test_same_email_does_not_require_password_or_reset_verification(accounts):
    client, first, _ = accounts
    old = login(client)
    result = client.put("/auth/user", json={"id": first, "email": "one@example.invalid", "name": "Same", "password": "wrong"})
    assert result.status_code == 200
    assert result.json()["data"]["email_verified"] is True
    assert result.json()["email_verification_required"] is False
    before = client.cookies.get("mainauth")
    failed = client.put("/auth/user", json={"id": first, "new_password": "Changed1!", "password": "wrong", "name": "Unwanted"})
    assert failed.json()["success"] is False
    assert client.cookies.get("mainauth") == before
    assert userdb.get_user(user_id=first)["name"] == "Same"
    assert old != before


def test_non_mainauth_key_uses_existing_jwt_behavior(accounts):
    client, first, _ = accounts
    token = JMT.make_jwt("other", {"name": "legacy"}, ["name"])
    client.cookies.set("otherkey", token, domain="testserver.local")
    response = client.get("/auth/isjwt", params={"key": "otherkey"})
    assert response.json()["data"] == {"name": "legacy"}
    assert "mainauth=" not in response.headers.get("set-cookie", "")


def test_duplicate_email_is_rejected_without_profile_or_cookie_change(accounts):
    client, first, _ = accounts
    login(client)
    before = client.cookies.get("mainauth")
    result = client.put("/auth/user", json={"id": first, "email": "two@example.invalid", "password": "Password1!"})
    assert result.status_code in (400, 409)
    assert userdb.get_user(user_id=first)["email"] == "one@example.invalid"
    assert client.cookies.get("mainauth") == before


def test_expired_cookie_and_invalid_update_leave_profile_untouched(accounts):
    client, first, _ = accounts
    login(client)
    before = client.cookies.get("mainauth")
    assert client.put("/auth/user", json={"id": first, "email": 123}).status_code == 422
    assert client.cookies.get("mainauth") == before
    expired = JMT.make_jwt(first, {"id": first, "email": "one@example.invalid", "name": "Old"}, ["id", "email", "name"], lifetime_seconds=-1)
    client.cookies.clear()
    client.cookies.set("mainauth", expired, domain="testserver.local")
    assert client.get("/auth/isjwt", params={"key": "mainauth"}).status_code == 401
    assert userdb.get_user(user_id=first)["name"] == "One"
