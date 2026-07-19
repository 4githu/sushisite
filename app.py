import sqlite3
import json
from dataclasses import dataclass
from typing import Optional

from fastapi import FastAPI, HTTPException

DB_NAME = "schedule.db"


def get_connection():
    con = sqlite3.connect(DB_NAME)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with get_connection() as con:
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS event_group (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_group_id INTEGER,
            color TEXT NOT NULL DEFAULT '#FFFFFF',
            metadata_schema TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(parent_group_id) REFERENCES event_group(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            group_id INTEGER,
            is_all_day INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'passive',
            type TEXT NOT NULL DEFAULT 'default',
            repeat_group_id INTEGER,
            color TEXT NOT NULL DEFAULT '#FFFFFF',
            memo TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(group_id) REFERENCES event_group(id)
        )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_event_start_time ON event(start_time)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_event_group ON event(group_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_group_parent ON event_group(parent_group_id)")


@dataclass
class Event:
    id: Optional[int]
    title: str
    start_time: str
    end_time: Optional[str] = None
    group_id: Optional[int] = None
    is_all_day: bool = False
    status: str = "passive"
    type: str = "default"
    repeat_group_id: Optional[int] = None
    color: str = "#FFFFFF"
    memo: str = ""
    metadata: dict = None

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            title=row["title"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            group_id=row["group_id"],
            is_all_day=bool(row["is_all_day"]),
            status=row["status"],
            type=row["type"],
            repeat_group_id=row["repeat_group_id"],
            color=row["color"],
            memo=row["memo"],
            metadata=json.loads(row["metadata"] or "{}")
        )

    def to_dict(self):
        return self.__dict__


@dataclass
class Group:
    id: Optional[int]
    name: str
    parent_group_id: Optional[int] = None
    color: str = "#FFFFFF"
    metadata_schema: dict = None

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            name=row["name"],
            parent_group_id=row["parent_group_id"],
            color=row["color"],
            metadata_schema=json.loads(row["metadata_schema"] or "{}")
        )

    def to_dict(self):
        return self.__dict__


class EventManager:

    @staticmethod
    def create(event: Event):
        if event.metadata is None:
            event.metadata = {}

        with get_connection() as con:
            cur = con.cursor()
            cur.execute("""
            INSERT INTO event (
                title,start_time,end_time,group_id,
                is_all_day,status,type,repeat_group_id,
                color,memo,metadata
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                event.title,
                event.start_time,
                event.end_time,
                event.group_id,
                int(event.is_all_day),
                event.status,
                event.type,
                event.repeat_group_id,
                event.color,
                event.memo,
                json.dumps(event.metadata)
            ))
            return cur.lastrowid

    @staticmethod
    def get(event_id: int):
        with get_connection() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM event WHERE id=?", (event_id,))
            row = cur.fetchone()
            return Event.from_row(row) if row else None

    @staticmethod
    def delete(event_id: int):
        with get_connection() as con:
            con.execute("DELETE FROM event WHERE id=?", (event_id,))

    @staticmethod
    def get_by_group(group_id: int):
        with get_connection() as con:
            cur = con.cursor()
            cur.execute("""
            SELECT * FROM event
            WHERE group_id=?
            ORDER BY start_time
            """, (group_id,))
            return [Event.from_row(r) for r in cur.fetchall()]


app = FastAPI(title="Schedule API")

init_db()


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/event")
def create_event(data: dict):
    event = Event(
        id=None,
        title=data["title"],
        start_time=data["start_time"],
        end_time=data.get("end_time"),
        group_id=data.get("group_id"),
        is_all_day=data.get("is_all_day", False),
        status=data.get("status", "passive"),
        type=data.get("type", "default"),
        repeat_group_id=data.get("repeat_group_id"),
        color=data.get("color", "#FFFFFF"),
        memo=data.get("memo", ""),
        metadata=data.get("metadata", {})
    )
    return {"id": EventManager.create(event)}


@app.get("/event/{event_id}")
def get_event(event_id: int):
    event = EventManager.get(event_id)
    if not event:
        raise HTTPException(404, "event not found")
    return event.to_dict()


@app.delete("/event/{event_id}")
def delete_event(event_id: int):
    EventManager.delete(event_id)
    return {"success": True}


@app.get("/group/{group_id}/events")
def get_group_events(group_id: int):
    return [e.to_dict() for e in EventManager.get_by_group(group_id)]
