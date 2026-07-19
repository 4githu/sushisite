from contextlib import contextmanager
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = (BASE_DIR.parent / "DB" / "sushiusers.db").resolve()
    
@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def get_user(email=None, user_id=None):
    if email is None and user_id is None:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()

        if user_id is not None:
            cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            )

        user = cursor.fetchone()

        conn.close()

        return user

def create_user(email, password_hash, name, created_at, email_verified=0):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (email, password_hash, name, created_at, email_verified) VALUES (?, ?, ?, ?, ?)", (email, password_hash, name, created_at, email_verified))
        conn.commit()
        conn.close()

def edit_user(id, email, password_hash, name, email_verified=0):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET email = ?, password_hash = ?, name = ?, email_verified = ? WHERE id = ?", (email, password_hash, name, email_verified, id))
        conn.commit()
        conn.close()

def delete_user(id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (id,))
        conn.commit()
        conn.close()

def make_imsi_user(email, password_hash, name, created_at, email_code):
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO imsi_users
            (email, password_hash, name, created_at, email_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, password_hash, name, created_at, email_code)
        )

        conn.commit()
        conn.close()

def get_imsi_user(email):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM imsi_users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        return user

def delete_imsi_user(email):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM imsi_users WHERE email = ?", (email,))
        conn.commit()
        conn.close()

