from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
import re
import sqlite3
import os

from .academic import (
    STAGE_TERM_PERIOD,
    canonical_school_name,
    parse_legacy_school_name,
    stage_for_date,
)


DB_PATH = Path(os.getenv('PERSONAL_PROJECT_DB_PATH', str(Path(__file__).resolve().parent / "personal_project.db")))


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
    term_period TEXT NOT NULL DEFAULT 'semester_1'
        CHECK (term_period IN ('semester_1', 'summer', 'semester_2', 'winter')),
    free_for_three_plus INTEGER NOT NULL DEFAULT 0,
    admission_year INTEGER NOT NULL DEFAULT 0,
    current_stage TEXT NOT NULL DEFAULT 'accepted',
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
    progress_stage TEXT NOT NULL DEFAULT 'accepted',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(school_id, round_number)
);
CREATE INDEX IF NOT EXISTS idx_aura_rounds_school
    ON aura_clinic_rounds(user_id, school_id, round_number);

-- 월별 정산은 사용자가 명시적으로 생성한 시점의 스냅샷을 보관한다.
CREATE TABLE IF NOT EXISTS aura_settlement_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    data_json TEXT NOT NULL,
    pricing_version INTEGER NOT NULL DEFAULT 2,
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, year, month)
);
CREATE INDEX IF NOT EXISTS idx_aura_settlement_snapshots_user_month
    ON aura_settlement_snapshots(user_id, year, month);

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
    progress_stage TEXT NOT NULL DEFAULT 'accepted',
    round_number INTEGER NOT NULL,
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(school_id, progress_stage, round_number, version)
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
    progress_stage TEXT NOT NULL DEFAULT 'accepted',
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
    ON clinic_report_score_formats(school_id, progress_stage, round_key, is_active, updated_at DESC);

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
            progress_stage TEXT NOT NULL DEFAULT 'accepted',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO aura_clinic_rounds_new
            (id, user_id, school_id, event_id, round_number, round_numbers_json,
             attendance_status, report_required, hourly_rate, amount,
             payment_status, legacy_session_id, series_group_id, series_index,
             progress_stage, created_at)
        SELECT id, user_id, school_id, event_id, round_number, round_numbers_json,
               attendance_status, report_required, hourly_rate, amount,
               payment_status, legacy_session_id, series_group_id, series_index,
               progress_stage, created_at
        FROM aura_clinic_rounds;
        DROP TABLE aura_clinic_rounds;
        ALTER TABLE aura_clinic_rounds_new RENAME TO aura_clinic_rounds;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def _replace_school_name_unique_constraint(conn: sqlite3.Connection) -> None:
    """A cohort school is unique regardless of its current academic stage."""
    correct_constraint = False
    for index in conn.execute("PRAGMA index_list(aura_schools)").fetchall():
        if not index[2]:
            continue
        columns = [
            row[2]
            for row in conn.execute(f"PRAGMA index_info('{index[1]}')").fetchall()
        ]
        if columns == ["user_id", "name"]:
            correct_constraint = True
            break
    if correct_constraint:
        return

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE aura_schools_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            default_hourly_rate INTEGER NOT NULL DEFAULT 30000,
            memo TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 0,
            term_status TEXT NOT NULL DEFAULT 'active'
                CHECK (term_status IN ('active', 'ended')),
            term_period TEXT NOT NULL DEFAULT 'semester_1'
                CHECK (term_period IN ('semester_1', 'summer', 'semester_2', 'winter')),
            free_for_three_plus INTEGER NOT NULL DEFAULT 0,
            admission_year INTEGER NOT NULL DEFAULT 0,
            current_stage TEXT NOT NULL DEFAULT 'accepted',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name)
        );
        INSERT INTO aura_schools_new
            (id, user_id, name, default_hourly_rate, memo, is_active, priority,
             term_status, term_period, free_for_three_plus, admission_year,
             current_stage, created_at)
        SELECT id, user_id, name, default_hourly_rate, memo, is_active, priority,
               term_status, term_period, free_for_three_plus, admission_year,
               current_stage, created_at
        FROM aura_schools;
        DROP TABLE aura_schools;
        ALTER TABLE aura_schools_new RENAME TO aura_schools;
        CREATE INDEX IF NOT EXISTS idx_aura_schools_user
            ON aura_schools(user_id, is_active, name);
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def _replace_round_template_unique_constraint(conn: sqlite3.Connection) -> None:
    correct_constraint = False
    for index in conn.execute("PRAGMA index_list(aura_round_templates)").fetchall():
        if not index[2]:
            continue
        columns = [
            row[2]
            for row in conn.execute(f"PRAGMA index_info('{index[1]}')").fetchall()
        ]
        if columns == ["school_id", "progress_stage", "round_number", "version"]:
            correct_constraint = True
            break
    if correct_constraint:
        return

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE aura_round_templates_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            school_id INTEGER NOT NULL REFERENCES aura_schools(id),
            progress_stage TEXT NOT NULL DEFAULT 'accepted',
            round_number INTEGER NOT NULL,
            version INTEGER NOT NULL,
            content_json TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(school_id, progress_stage, round_number, version)
        );
        INSERT INTO aura_round_templates_new
            (id, user_id, school_id, progress_stage, round_number, version,
             content_json, is_active, created_at)
        SELECT id, user_id, school_id, progress_stage, round_number, version,
               content_json, is_active, created_at
        FROM aura_round_templates;
        DROP TABLE aura_round_templates;
        ALTER TABLE aura_round_templates_new RENAME TO aura_round_templates;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def _legacy_folder_stage(name: str) -> str | None:
    if name.strip() == "심층":
        return "deep"
    match = re.search(r"(?:^|\s)([123])-([12])(?:\s|$)", name)
    if match:
        return f"grade{match.group(1)}_semester{match.group(2)}"
    return None


def _migrate_school_progression(conn: sqlite3.Connection) -> None:
    """Merge legacy term folders into one cohort school while preserving each round's stage."""
    schools = conn.execute("SELECT * FROM aura_schools ORDER BY id").fetchall()
    if not schools:
        return

    identities: dict[int, tuple[int, str, str]] = {}
    for school in schools:
        admission_year, base_name = parse_legacy_school_name(school["name"])
        canonical = canonical_school_name(admission_year, base_name)
        identities[school["id"]] = (admission_year, base_name, canonical)
        override = _legacy_folder_stage(school["name"])
        stages = []
        rounds = conn.execute(
            """SELECT r.id, r.round_number, r.event_id, e.start_time
               FROM aura_clinic_rounds r
               JOIN events e ON e.id = r.event_id
               WHERE r.school_id = ?""",
            (school["id"],),
        ).fetchall()
        for round_row in rounds:
            start = datetime.fromisoformat(round_row["start_time"].replace("Z", "+00:00"))
            stage = override or stage_for_date(admission_year, start)
            stages.append(stage)
            conn.execute(
                "UPDATE aura_clinic_rounds SET progress_stage = ? WHERE id = ?",
                (stage, round_row["id"]),
            )
        default_stage = override or (max(set(stages), key=stages.count) if stages else stage_for_date(admission_year, date.today()))
        templates = conn.execute(
            "SELECT id, round_number FROM aura_round_templates WHERE school_id = ?",
            (school["id"],),
        ).fetchall()
        for template in templates:
            matching = conn.execute(
                """SELECT progress_stage, COUNT(*) AS count
                   FROM aura_clinic_rounds
                   WHERE school_id = ?
                     AND (round_number = ? OR EXISTS (
                         SELECT 1 FROM json_each(round_numbers_json) WHERE value = ?
                     ))
                   GROUP BY progress_stage ORDER BY count DESC LIMIT 1""",
                (school["id"], template["round_number"], template["round_number"]),
            ).fetchone()
            conn.execute(
                "UPDATE aura_round_templates SET progress_stage = ? WHERE id = ?",
                (matching["progress_stage"] if matching else default_stage, template["id"]),
            )
        conn.execute(
            "UPDATE clinic_report_score_formats SET progress_stage = ? WHERE school_id = ?",
            (default_stage, school["id"]),
        )

    grouped: dict[tuple[int, str], list] = {}
    for school in schools:
        canonical = identities[school["id"]][2]
        grouped.setdefault((school["user_id"], canonical), []).append(school)

    for (_, canonical), group in grouped.items():
        keeper = next((school for school in group if school["name"] == canonical), group[0])
        admission_year = identities[keeper["id"]][0]
        is_deep = identities[keeper["id"]][1] == "심층"
        current_stage = "deep" if is_deep else stage_for_date(admission_year, date.today())
        memos = list(dict.fromkeys(school["memo"].strip() for school in group if school["memo"].strip()))
        for source in group:
            if source["id"] == keeper["id"]:
                continue
            conn.execute(
                "UPDATE aura_clinic_rounds SET school_id = ? WHERE school_id = ?",
                (keeper["id"], source["id"]),
            )
            conn.execute(
                "UPDATE aura_round_templates SET school_id = ? WHERE school_id = ?",
                (keeper["id"], source["id"]),
            )
            conn.execute(
                "UPDATE clinic_report_score_formats SET school_id = ? WHERE school_id = ?",
                (keeper["id"], source["id"]),
            )
            setting = conn.execute(
                "SELECT 1 FROM clinic_report_generation_settings WHERE school_id = ?",
                (source["id"],),
            ).fetchone()
            if setting:
                keeper_setting = conn.execute(
                    "SELECT 1 FROM clinic_report_generation_settings WHERE school_id = ?",
                    (keeper["id"],),
                ).fetchone()
                if keeper_setting:
                    conn.execute(
                        "DELETE FROM clinic_report_generation_settings WHERE school_id = ?",
                        (source["id"],),
                    )
                else:
                    conn.execute(
                        "UPDATE clinic_report_generation_settings SET school_id = ? WHERE school_id = ?",
                        (keeper["id"], source["id"]),
                    )
            conn.execute("DELETE FROM aura_schools WHERE id = ?", (source["id"],))

        conn.execute(
            """UPDATE aura_schools
               SET name = ?, admission_year = ?, current_stage = ?, term_period = ?,
                   memo = ?, priority = ?, is_active = ?, term_status = ?,
                   free_for_three_plus = ?
               WHERE id = ?""",
            (
                canonical,
                admission_year,
                current_stage,
                STAGE_TERM_PERIOD[current_stage],
                "\n".join(memos),
                max(school["priority"] for school in group),
                max(school["is_active"] for school in group),
                "active" if any(school["term_status"] == "active" for school in group) else "ended",
                max(school["free_for_three_plus"] for school in group),
                keeper["id"],
            ),
        )
        round_rows = conn.execute(
            "SELECT event_id, round_numbers_json, round_number FROM aura_clinic_rounds WHERE school_id = ?",
            (keeper["id"],),
        ).fetchall()
        for round_row in round_rows:
            numbers = round_row["round_numbers_json"].strip("[]") or str(round_row["round_number"])
            conn.execute(
                "UPDATE events SET title = ? WHERE id = ?",
                (f"{canonical} {numbers.replace(' ', '')}회차 클리닉", round_row["event_id"]),
            )


def _refresh_clinic_round_amounts(conn: sqlite3.Connection) -> None:
    """Keep historical clinic rates exact, without SQLite floating-point minute loss."""
    conn.execute(
        """
        UPDATE aura_clinic_rounds
        SET hourly_rate = (
            SELECT ROUND(
                CASE WHEN aura_clinic_rounds.progress_stage = 'deep' THEN 40000
                WHEN (SELECT COUNT(*) FROM aura_round_targets t WHERE t.round_id = aura_clinic_rounds.id) <= 3 THEN 30000
                ELSE (SELECT COUNT(*) FROM aura_round_targets t WHERE t.round_id = aura_clinic_rounds.id) * 10000 END
            )
        ),
        amount = (
            SELECT ROUND(
                (CASE WHEN aura_clinic_rounds.progress_stage = 'deep' THEN 40000
                 WHEN (SELECT COUNT(*) FROM aura_round_targets t WHERE t.round_id = aura_clinic_rounds.id) <= 3 THEN 30000
                 ELSE (SELECT COUNT(*) FROM aura_round_targets t WHERE t.round_id = aura_clinic_rounds.id) * 10000 END)
                * MAX(0, ROUND(
                    (CAST(strftime('%s', e.end_time) AS INTEGER) - CAST(strftime('%s', e.start_time) AS INTEGER))
                    / 1800.0
                )) / 2.0
            )
            FROM events e WHERE e.id = aura_clinic_rounds.event_id
        )
        """
    )


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
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
        added_progression = "progress_stage" not in round_columns
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
        if "progress_stage" not in round_columns:
            conn.execute(
                """ALTER TABLE aura_clinic_rounds ADD COLUMN progress_stage
                   TEXT NOT NULL DEFAULT 'accepted'"""
            )
        school_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(aura_schools)")
        }
        added_progression = added_progression or any(
            name not in school_columns for name in ("admission_year", "current_stage")
        )
        if "priority" not in school_columns:
            conn.execute(
                "ALTER TABLE aura_schools ADD COLUMN priority INTEGER NOT NULL DEFAULT 0"
            )
        if "term_status" not in school_columns:
            conn.execute(
                """ALTER TABLE aura_schools ADD COLUMN term_status TEXT
                   NOT NULL DEFAULT 'active'"""
            )
        if "term_period" not in school_columns:
            conn.execute(
                """ALTER TABLE aura_schools ADD COLUMN term_period TEXT
                   NOT NULL DEFAULT 'semester_1'"""
            )
        if "admission_year" not in school_columns:
            conn.execute(
                "ALTER TABLE aura_schools ADD COLUMN admission_year INTEGER NOT NULL DEFAULT 0"
            )
        if "current_stage" not in school_columns:
            conn.execute(
                """ALTER TABLE aura_schools ADD COLUMN current_stage
                   TEXT NOT NULL DEFAULT 'accepted'"""
            )
        snapshot_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(aura_settlement_snapshots)")
        }
        if "pricing_version" not in snapshot_columns:
            # 기존 스냅샷은 다대일 조교 정산 규칙 전 결과이므로 재생성을 요구한다.
            conn.execute(
                """ALTER TABLE aura_settlement_snapshots ADD COLUMN pricing_version
                   INTEGER NOT NULL DEFAULT 1"""
            )
        added_free_option = "free_for_three_plus" not in school_columns
        if added_free_option:
            conn.execute(
                """ALTER TABLE aura_schools ADD COLUMN free_for_three_plus
                   INTEGER NOT NULL DEFAULT 0"""
            )
            conn.execute(
                """UPDATE aura_schools SET free_for_three_plus = 1
                   WHERE name NOT LIKE '%심층%'
                     AND (name LIKE '%서울%' OR name LIKE '%경기%' OR name LIKE '%한성%')"""
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
        template_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(aura_round_templates)")
        }
        if "progress_stage" not in template_columns:
            conn.execute(
                """ALTER TABLE aura_round_templates ADD COLUMN progress_stage
                   TEXT NOT NULL DEFAULT 'accepted'"""
            )
        score_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(clinic_report_score_formats)")
        }
        if "progress_stage" not in score_columns:
            conn.execute(
                """ALTER TABLE clinic_report_score_formats ADD COLUMN progress_stage
                   TEXT NOT NULL DEFAULT 'accepted'"""
            )
        _replace_round_template_unique_constraint(conn)
        if added_progression:
            _migrate_school_progression(conn)
            conn.execute("UPDATE aura_settlement_snapshots SET pricing_version = 1")
        _replace_school_name_unique_constraint(conn)
        _remove_school_round_unique_constraint(conn)
        _refresh_clinic_round_amounts(conn)
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_events_recurrence
               ON events(user_id, recurrence_group_id, recurrence_index)"""
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_aura_round_series
               ON aura_clinic_rounds(user_id, series_group_id, series_index)"""
        )
        conn.execute("DROP INDEX IF EXISTS idx_clinic_score_formats_round")
        conn.execute(
            """CREATE INDEX idx_clinic_score_formats_round
               ON clinic_report_score_formats(
                   school_id, progress_stage, round_key, is_active, updated_at DESC
               )"""
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
