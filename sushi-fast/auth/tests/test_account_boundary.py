"""HTTP authorization regression using only a disposable SQLite database."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import JMT, router, sushihash, userdb


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-users.db"
    monkeypatch.setattr(userdb, "DB_PATH", path)
    monkeypatch.setattr(JMT, "SECRET_KEY", "synthetic-test-only-secret")
    monkeypatch.setattr(JMT, "ALGORITHM", "HS256")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, name TEXT, created_at INTEGER, email_verified INTEGER)")
    userdb.create_user("one@example.invalid", sushihash.make_hash("Password1!"), "One", 1, email_verified=1)
    userdb.create_user("two@example.invalid", sushihash.make_hash("Password2!"), "Two", 1, email_verified=1)
    app = FastAPI()
    app.include_router(router.router)
    client = TestClient(app)
    first = userdb.get_user("one@example.invalid")
    second = userdb.get_user("two@example.invalid")
    return client, first["id"], second["id"]


def _login(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200 and response.json()["success"]


@pytest.mark.parametrize("method", ["put", "delete"])
def test_anonymous_cannot_modify_accounts(accounts, method):
    client, first, _ = accounts
    response = (client.put("/auth/user", json={"id": first, "name": "Intruder"}) if method == "put"
                else client.request("DELETE", f"/auth/user/{first}", json={"password": "Password1!"}))
    assert response.status_code == 401
    assert userdb.get_user(user_id=first)["name"] == "One"


@pytest.mark.parametrize("method", ["put", "delete"])
def test_authenticated_user_cannot_modify_another_account(accounts, method):
    client, first, second = accounts
    _login(client, "one@example.invalid", "Password1!")
    response = (client.put("/auth/user", json={"id": second, "name": "Intruder"}) if method == "put"
                else client.request("DELETE", f"/auth/user/{second}", json={"password": "Password2!"}))
    assert response.status_code == 403
    assert userdb.get_user(user_id=second)["name"] == "Two"


def test_own_profile_update_returns_only_public_fields(accounts):
    client, first, _ = accounts
    _login(client, "one@example.invalid", "Password1!")
    response = client.put("/auth/user", json={"id": first, "name": "Updated"})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": None, "data": {"id": first, "email": "one@example.invalid", "name": "Updated", "email_verified": True}, "email_verification_required": False}
    assert userdb.get_user(user_id=first)["email_verified"] == 1


def test_email_change_requires_current_password(accounts):
    client, first, _ = accounts
    _login(client, "one@example.invalid", "Password1!")
    response = client.put("/auth/user", json={"id": first, "email": "changed@example.invalid"})
    assert response.status_code == 403
    assert userdb.get_user(user_id=first)["email"] == "one@example.invalid"


def test_email_change_with_password_succeeds_and_resets_verification(accounts):
    client, first, _ = accounts
    _login(client, "one@example.invalid", "Password1!")
    response = client.put("/auth/user", json={"id": first, "email": "changed@example.invalid", "password": "Password1!"})
    assert response.status_code == 200 and response.json()["data"]["email"] == "changed@example.invalid"
    assert userdb.get_user(user_id=first)["email_verified"] == 0


def test_forged_session_cannot_modify_accounts(accounts):
    client, first, _ = accounts
    client.cookies.set("mainauth", "invalid.synthetic.jwt")
    assert client.put("/auth/user", json={"id": first, "name": "Intruder"}).status_code == 401
    assert client.request("DELETE", f"/auth/user/{first}", json={"password": "Password1!"}).status_code == 401
    assert userdb.get_user(user_id=first)["name"] == "One"


def test_own_password_change_requires_current_password(accounts):
    client, first, _ = accounts
    _login(client, "one@example.invalid", "Password1!")
    response = client.put("/auth/user", json={"id": first, "password": "Password1!", "new_password": "Changed1!"})
    assert response.status_code == 200
    assert sushihash.check_hash("Changed1!", userdb.get_user(user_id=first)["password_hash"])
    assert set(response.json()["data"]) == {"id", "email", "name", "email_verified"}


def test_verification_endpoints_never_return_password_hash(accounts, monkeypatch):
    from auth import service
    client, first, _ = accounts
    user = userdb.get_user(user_id=first)
    monkeypatch.setattr(service, "verify_login_code", lambda *_: (True, user))
    monkeypatch.setattr(service, "verify_register_code", lambda *_: (True, user))
    for endpoint in ("/auth/login/verify", "/auth/register/verify"):
        response = client.post(endpoint, json={"email": "one@example.invalid", "code": "synthetic"})
        assert response.status_code == 200
        assert response.json()["data"] == {"id": first, "email": "one@example.invalid", "name": "One"}


def test_own_delete_requires_password_and_removes_only_self(accounts):
    client, first, second = accounts
    _login(client, "one@example.invalid", "Password1!")
    assert client.request("DELETE", f"/auth/user/{first}", json={}).status_code in (403, 422)
    assert client.request("DELETE", f"/auth/user/{first}", json={"password": "wrong"}).status_code == 403
    assert userdb.get_user(user_id=first) is not None
    response = client.request("DELETE", f"/auth/user/{first}", json={"password": "Password1!"})
    assert response.status_code == 200 and response.json() == {"success": True}
    assert userdb.get_user(user_id=first) is None
    assert userdb.get_user(user_id=second) is not None
