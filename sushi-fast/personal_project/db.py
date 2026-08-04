from contextlib import contextmanager
from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parent / "personal_project.db"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    start_time TEXT NOT NULL,
    end_time TEXT,
    is_all_day INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'todo'
        CHECK (status IN ('passive', 'todo', 'done')),
    type TEXT NOT NULL DEFAULT 'personal',
    group_name TEXT,
    category_name TEXT,
    recurrence_group_id TEXT,
    recurrence_index INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_time IS NULL OR end_time >= start_time)
);
CREATE INDEX IF NOT EXISTS idx_events_user_start
    ON events(user_id, start_time);

CREATE TABLE IF NOT EXISTS aura_students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    school_name TEXT NOT NULL DEFAULT '',
    affiliation TEXT NOT NULL DEFAULT '',
    memo TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_aura_students_user
    ON aura_students(user_id, is_active, name);

CREATE TABLE IF NOT EXISTS aura_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES aura_students(id),
    session_number INTEGER NOT NULL,
    attendance_status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (attendance_status IN ('scheduled', 'completed', 'cancelled', 'absent')),
    report_required INTEGER NOT NULL DEFAULT 1,
    hourly_rate INTEGER NOT NULL DEFAULT 30000,
    amount INTEGER NOT NULL DEFAULT 0,
    school_name_snapshot TEXT NOT NULL DEFAULT '',
    payment_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (payment_status IN ('pending', 'paid')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_aura_sessions_user_student
    ON aura_sessions(user_id, student_id);

CREATE TABLE IF NOT EXISTS aura_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aura_session_id INTEGER NOT NULL UNIQUE
        REFERENCES aura_sessions(id) ON DELETE CASCADE,
    content_json TEXT NOT NULL DEFAULT '{"type":"doc","content":[]}',
    source_notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'ready', 'submitted')),
    submitted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS aura_schools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    default_hourly_rate INTEGER NOT NULL DEFAULT 30000,
    memo TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 0,
    term_status TEXT NOT NULL DEFAULT 'active'
        CHECK (term_status IN ('active', 'ended')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_aura_schools_user
    ON aura_schools(user_id, is_active, name);

CREATE TABLE IF NOT EXISTS aura_clinic_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    school_id INTEGER NOT NULL REFERENCES aura_schools(id),
    event_id INTEGER NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    round_numbers_json TEXT NOT NULL DEFAULT '[]',
    attendance_status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (attendance_status IN ('scheduled', 'completed', 'cancelled')),
    report_required INTEGER NOT NULL DEFAULT 1,
    hourly_rate INTEGER NOT NULL DEFAULT 30000,
    amount INTEGER NOT NULL DEFAULT 0,
    payment_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (payment_status IN ('pending', 'paid')),
    legacy_session_id INTEGER UNIQUE,
    series_group_id TEXT,
    series_index INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(school_id, round_number)
);
CREATE INDEX IF NOT EXISTS idx_aura_rounds_school
    ON aura_clinic_rounds(user_id, school_id, round_number);

CREATE TABLE IF NOT EXISTS aura_round_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL REFERENCES aura_clinic_rounds(id) ON DELETE CASCADE,
    student_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_aura_targets_round
    ON aura_round_targets(round_id, sort_order, id);

CREATE TABLE IF NOT EXISTS aura_round_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    school_id INTEGER NOT NULL REFERENCES aura_schools(id),
    round_number INTEGER NOT NULL,
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(school_id, round_number, version)
);

CREATE TABLE IF NOT EXISTS aura_target_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL UNIQUE REFERENCES aura_round_targets(id) ON DELETE CASCADE,
    template_id INTEGER REFERENCES aura_round_templates(id),
    template_version INTEGER,
    content_json TEXT NOT NULL,
    source_notes TEXT NOT NULL DEFAULT '',
    question_checks_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'ready', 'submitted')),
    has_user_edits INTEGER NOT NULL DEFAULT 0,
    lecture_progress INTEGER NOT NULL DEFAULT 5,
    lecture_comprehension INTEGER NOT NULL DEFAULT 5,
    memory_before INTEGER NOT NULL DEFAULT 4,
    memory_after INTEGER NOT NULL DEFAULT 5,
    assessment_json TEXT NOT NULL DEFAULT '{"formatName":"","items":[]}',
    generated_report_json TEXT,
    ai_model TEXT,
    submitted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 원본 이미지는 최종 제출 전까지만 보관하는 임시 첨부입니다.
CREATE TABLE IF NOT EXISTS aura_report_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_report_id INTEGER NOT NULL REFERENCES aura_target_reports(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('blank_test', 'problem_solving')),
    original_name TEXT NOT NULL DEFAULT '',
    mime_type TEXT NOT NULL,
    storage_name TEXT NOT NULL UNIQUE,
    byte_size INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_aura_report_attachments_report
    ON aura_report_attachments(target_report_id, kind, id);

CREATE TABLE IF NOT EXISTS clinic_report_score_formats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    school_id INTEGER NOT NULL REFERENCES aura_schools(id) ON DELETE CASCADE,
    round_key TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    items_json TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'generated'
        CHECK(source IN ('generated', 'manual')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clinic_score_formats_round
    ON clinic_report_score_formats(school_id, round_key, is_active, updated_at DESC);

CREATE TABLE IF NOT EXISTS clinic_report_generation_settings (
    user_id INTEGER NOT NULL,
    school_id INTEGER NOT NULL REFERENCES aura_schools(id) ON DELETE CASCADE,
    score_mode TEXT NOT NULL DEFAULT 'auto'
        CHECK(score_mode IN ('auto', 'none')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, school_id)
);

CREATE TABLE IF NOT EXISTS personal_kakao_connections (
    user_id INTEGER PRIMARY KEY,
    kakao_user_id TEXT,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    access_expires_at TEXT NOT NULL,
    refresh_expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS personal_kakao_oauth_states (
    state TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    return_to TEXT NOT NULL DEFAULT '/personal-project/aura',
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _remove_school_round_unique_constraint(conn: sqlite3.Connection) -> None:
    unique_school_round = False
    for index in conn.execute("PRAGMA index_list(aura_clinic_rounds)").fetchall():
        if not index[2]:
            continue
        columns = [
            row[2]
            for row in conn.execute(f"PRAGMA index_info('{index[1]}')").fetchall()
        ]
        if columns == ["school_id", "round_number"]:
            unique_school_round = True
            break
    if not unique_school_round:
        return

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE aura_clinic_rounds_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            school_id INTEGER NOT NULL REFERENCES aura_schools(id),
            event_id INTEGER NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
            round_number INTEGER NOT NULL,
            round_numbers_json TEXT NOT NULL DEFAULT '[]',
            attendance_status TEXT NOT NULL DEFAULT 'scheduled'
                CHECK (attendance_status IN ('scheduled', 'completed', 'cancelled')),
            report_required INTEGER NOT NULL DEFAULT 1,
            hourly_rate INTEGER NOT NULL DEFAULT 30000,
            amount INTEGER NOT NULL DEFAULT 0,
            payment_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (payment_status IN ('pending', 'paid')),
            legacy_session_id INTEGER UNIQUE,
            series_group_id TEXT,
            series_index INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO aura_clinic_rounds_new
            (id, user_id, school_id, event_id, round_number, round_numbers_json,
             attendance_status, report_required, hourly_rate, amount,
             payment_status, legacy_session_id, series_group_id, series_index,
             created_at)
        SELECT id, user_id, school_id, event_id, round_number, round_numbers_json,
               attendance_status, report_required, hourly_rate, amount,
               payment_status, legacy_session_id, series_group_id, series_index,
               created_at
        FROM aura_clinic_rounds;
        DROP TABLE aura_clinic_rounds;
        ALTER TABLE aura_clinic_rounds_new RENAME TO aura_clinic_rounds;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(aura_sessions)")}
        if "hourly_rate" not in columns:
            conn.execute(
                "ALTER TABLE aura_sessions ADD COLUMN hourly_rate INTEGER NOT NULL DEFAULT 30000"
            )
        event_columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
        if "recurrence_group_id" not in event_columns:
            conn.execute("ALTER TABLE events ADD COLUMN recurrence_group_id TEXT")
        if "recurrence_index" not in event_columns:
            conn.execute("ALTER TABLE events ADD COLUMN recurrence_index INTEGER")
        round_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(aura_clinic_rounds)")
        }
        if "series_group_id" not in round_columns:
            conn.execute("ALTER TABLE aura_clinic_rounds ADD COLUMN series_group_id TEXT")
        if "series_index" not in round_columns:
            conn.execute("ALTER TABLE aura_clinic_rounds ADD COLUMN series_index INTEGER")
        if "round_numbers_json" not in round_columns:
            conn.execute(
                "ALTER TABLE aura_clinic_rounds ADD COLUMN round_numbers_json TEXT NOT NULL DEFAULT '[]'"
            )
            conn.execute(
                """UPDATE aura_clinic_rounds
                   SET round_numbers_json = '[' || round_number || ']'
                   WHERE round_numbers_json = '[]'"""
            )
        school_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(aura_schools)")
        }
        if "priority" not in school_columns:
            conn.execute(
                "ALTER TABLE aura_schools ADD COLUMN priority INTEGER NOT NULL DEFAULT 0"
            )
        if "term_status" not in school_columns:
            conn.execute(
                """ALTER TABLE aura_schools ADD COLUMN term_status TEXT
                   NOT NULL DEFAULT 'active'"""
            )
        report_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(aura_target_reports)")
        }
        if "has_user_edits" not in report_columns:
            conn.execute(
                """ALTER TABLE aura_target_reports ADD COLUMN has_user_edits
                   INTEGER NOT NULL DEFAULT 0"""
            )
        if "question_checks_json" not in report_columns:
            conn.execute(
                """ALTER TABLE aura_target_reports ADD COLUMN question_checks_json
                   TEXT NOT NULL DEFAULT '{}'"""
            )
        report_additions = {
            "lecture_progress": "INTEGER NOT NULL DEFAULT 5",
            "lecture_comprehension": "INTEGER NOT NULL DEFAULT 5",
            "memory_before": "INTEGER NOT NULL DEFAULT 4",
            "memory_after": "INTEGER NOT NULL DEFAULT 5",
            "assessment_json": (
                "TEXT NOT NULL DEFAULT '{\"formatName\":\"\",\"items\":[]}'"
            ),
            "generated_report_json": "TEXT",
            "ai_model": "TEXT",
        }
        for name, declaration in report_additions.items():
            if name not in report_columns:
                conn.execute(
                    f"ALTER TABLE aura_target_reports ADD COLUMN {name} {declaration}"
                )
        _remove_school_round_unique_constraint(conn)
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_events_recurrence
               ON events(user_id, recurrence_group_id, recurrence_index)"""
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_aura_round_series
               ON aura_clinic_rounds(user_id, series_group_id, series_index)"""
        )
        conn.commit()


@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


init_db()
