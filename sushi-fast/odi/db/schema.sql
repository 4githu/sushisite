-- odi/db/schema.sql

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    auth_id TEXT UNIQUE,
    recent_template TEXT,
    config TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    CHECK (recent_template IS NULL OR json_valid(recent_template)),
    CHECK (json_valid(config))
);

CREATE TABLE IF NOT EXISTS templates (
    template_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    template TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (owner_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CHECK (json_valid(template))
);

CREATE TABLE IF NOT EXISTS pre_sessions (
    pin_code TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    session_id TEXT,
    state TEXT NOT NULL DEFAULT 'waiting',
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (template_id) REFERENCES templates(template_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE SET NULL,
    CHECK (state IN ('waiting', 'running', 'finished', 'expired', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    template_id TEXT,
    template TEXT NOT NULL,
    feedback TEXT,
    state TEXT NOT NULL DEFAULT 'running',
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES templates(template_id) ON DELETE SET NULL,
    CHECK (json_valid(template)),
    CHECK (feedback IS NULL OR json_valid(feedback)),
    CHECK (state IN ('running', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_users_auth_id ON users(auth_id);
CREATE INDEX IF NOT EXISTS idx_templates_owner_id ON templates(owner_id);
CREATE INDEX IF NOT EXISTS idx_pre_sessions_template_id ON pre_sessions(template_id);
CREATE INDEX IF NOT EXISTS idx_pre_sessions_session_id ON pre_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_pre_sessions_expires_at ON pre_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_template_id ON sessions(template_id);

CREATE TABLE IF NOT EXISTS presentation_segments (
    evc_session_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    owner_user_id TEXT,
    pre_session_pin TEXT,
    segment_json TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (evc_session_id, step),
    CHECK (json_valid(segment_json))
);

CREATE TABLE IF NOT EXISTS presentation_reactions (
    evc_session_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    owner_user_id TEXT,
    pre_session_pin TEXT,
    reaction_json TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (evc_session_id, sequence),
    CHECK (json_valid(reaction_json))
);

CREATE TABLE IF NOT EXISTS presentation_report_jobs (
    job_id TEXT PRIMARY KEY,
    evc_session_id TEXT NOT NULL,
    request_id TEXT NOT NULL UNIQUE,
    odi_session_id TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (status IN ('queued', 'generating', 'ready', 'failed')),
    FOREIGN KEY (odi_session_id) REFERENCES sessions(session_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS presentation_reports (
    report_id TEXT PRIMARY KEY,
    evc_session_id TEXT NOT NULL UNIQUE,
    odi_session_id TEXT,
    version TEXT NOT NULL,
    feedback_json TEXT NOT NULL,
    generator TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (json_valid(feedback_json)),
    FOREIGN KEY (odi_session_id) REFERENCES sessions(session_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_presentation_segments_expiry ON presentation_segments(expires_at);
CREATE INDEX IF NOT EXISTS idx_presentation_reactions_expiry ON presentation_reactions(expires_at);
CREATE INDEX IF NOT EXISTS idx_report_jobs_evc_session ON presentation_report_jobs(evc_session_id);
CREATE INDEX IF NOT EXISTS idx_reports_odi_session ON presentation_reports(odi_session_id);

CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    UPDATE users
    SET updated_at = datetime('now')
    WHERE user_id = OLD.user_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_templates_updated_at
AFTER UPDATE ON templates
FOR EACH ROW
BEGIN
    UPDATE templates
    SET updated_at = datetime('now')
    WHERE template_id = OLD.template_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_sessions_updated_at
AFTER UPDATE ON sessions
FOR EACH ROW
BEGIN
    UPDATE sessions
    SET updated_at = datetime('now')
    WHERE session_id = OLD.session_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_presentation_segments_updated_at
AFTER UPDATE ON presentation_segments
FOR EACH ROW
BEGIN
    UPDATE presentation_segments
    SET updated_at = datetime('now')
    WHERE evc_session_id = OLD.evc_session_id AND step = OLD.step;
END;

CREATE TRIGGER IF NOT EXISTS trg_presentation_reactions_updated_at
AFTER UPDATE ON presentation_reactions
FOR EACH ROW
BEGIN
    UPDATE presentation_reactions
    SET updated_at = datetime('now')
    WHERE evc_session_id = OLD.evc_session_id AND sequence = OLD.sequence;
END;

CREATE TRIGGER IF NOT EXISTS trg_report_jobs_updated_at
AFTER UPDATE ON presentation_report_jobs
FOR EACH ROW
BEGIN
    UPDATE presentation_report_jobs
    SET updated_at = datetime('now')
    WHERE job_id = OLD.job_id;
END;
