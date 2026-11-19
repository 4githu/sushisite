"""Independent player database. Only user IDs are shared with Sushi auth."""
from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3

DB_PATH = Path(os.getenv("PERSONAL_PLAYER_DB_PATH", Path(__file__).with_name("player.db")))

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS collections (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL,
 mode TEXT NOT NULL DEFAULT 'ordered' CHECK(mode IN ('ordered','weighted')),
 repeat_mode TEXT NOT NULL DEFAULT 'all' CHECK(repeat_mode IN ('all','one','off')),
 avoid_repeat INTEGER NOT NULL DEFAULT 1, playback_rate REAL NOT NULL DEFAULT 2,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS collections_owner ON collections(user_id,updated_at DESC);
CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY, collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
 playlist_id TEXT NOT NULL, title TEXT NOT NULL, source_url TEXT NOT NULL,
 account_id INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tracks (
 id INTEGER PRIMARY KEY, collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
 source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
 video_id TEXT NOT NULL, title TEXT NOT NULL, channel_title TEXT NOT NULL DEFAULT '',
 thumbnail_url TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL,
 weight REAL NOT NULL DEFAULT 1 CHECK(weight BETWEEN 0.1 AND 10),
 enabled INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS tracks_order ON tracks(collection_id,position,id);
CREATE TABLE IF NOT EXISTS google_accounts (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT NOT NULL,
 email TEXT NOT NULL, client_kind TEXT NOT NULL, refresh_token TEXT NOT NULL,
 scopes TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(user_id,subject)
);
CREATE INDEX IF NOT EXISTS google_accounts_owner ON google_accounts(user_id);
"""


def initialize() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=15) as db:
        db.executescript(SCHEMA)
        # Existing player databases used an INTEGER weight with a 1–5 CHECK.
        # SQLite cannot alter that constraint in place, so copy the rows once.
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("BEGIN IMMEDIATE")
        weight_type = next(row[2] for row in db.execute("PRAGMA table_info(tracks)") if row[1] == "weight")
        if weight_type.upper() == "INTEGER":
            db.execute("""CREATE TABLE tracks_real (
                id INTEGER PRIMARY KEY, collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
                video_id TEXT NOT NULL, title TEXT NOT NULL, channel_title TEXT NOT NULL DEFAULT '',
                thumbnail_url TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL,
                weight REAL NOT NULL DEFAULT 1 CHECK(weight BETWEEN 0.1 AND 10),
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            db.execute("""INSERT INTO tracks_real
                (id,collection_id,source_id,video_id,title,channel_title,thumbnail_url,position,weight,enabled,created_at)
                SELECT id,collection_id,source_id,video_id,title,channel_title,thumbnail_url,position,weight,enabled,created_at
                FROM tracks""")
            db.execute("DROP TABLE tracks")
            db.execute("ALTER TABLE tracks_real RENAME TO tracks")
            db.execute("CREATE INDEX tracks_order ON tracks(collection_id,position,id)")
        db.commit()


@contextmanager
def connection():
    initialize()
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
