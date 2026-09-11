import sqlite3

from auth import email_verified, service, sushihash, userdb


def _create_users_table(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                email_verified INTEGER NOT NULL DEFAULT 0
            )
            """
        )


def test_password_reset_changes_only_the_password(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    _create_users_table(db_path)
    monkeypatch.setattr(userdb, "DB_PATH", db_path)
    monkeypatch.setattr(email_verified, "send_verification_email", lambda *_: "123456")

    userdb.create_user("user@example.com", sushihash.make_hash("Oldpass1!"), "테스트", 1, email_verified=1)

    assert service.request_password_reset("user@example.com") is True
    success, message = service.reset_password("user@example.com", "123456", "Newpass1!")

    assert success is True
    assert message is None
    user = userdb.get_user("user@example.com")
    assert user["name"] == "테스트"
    assert user["email_verified"] == 1
    assert sushihash.check_hash("Newpass1!", user["password_hash"])
    assert userdb.get_password_reset_code("user@example.com") is None


def test_long_password_login_returns_message_instead_of_500(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    _create_users_table(db_path)
    monkeypatch.setattr(userdb, "DB_PATH", db_path)
    userdb.create_user("user@example.com", sushihash.make_hash("Validpass1!"), "테스트", 1)

    success, message = service.login_with_password("user@example.com", "a" * 100)

    assert success is False
    assert "재설정" in message
