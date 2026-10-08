"""Publish Aura state into generic calendar fields, including historical events."""

def install(db):
    db.executescript("""
    CREATE VIEW IF NOT EXISTS aura_calendar_state AS
    SELECT c.event_id,
      CASE WHEN c.report_required=0 OR c.attendance_status='cancelled' THEN 'passive'
           WHEN EXISTS(SELECT 1 FROM aura_round_targets t WHERE t.round_id=c.id)
            AND NOT EXISTS(SELECT 1 FROM aura_round_targets t
              LEFT JOIN aura_target_reports r ON r.target_id=t.id
              WHERE t.round_id=c.id AND COALESCE(r.status,'draft')!='submitted')
           THEN 'done' ELSE 'todo' END AS status,
      '/personal-project/aura/schools/' || c.school_id AS url
    FROM aura_clinic_rounds c
    UNION ALL
    SELECT s.event_id,
      CASE WHEN s.report_required=0 OR s.attendance_status IN ('cancelled','absent') THEN 'passive'
           WHEN r.status='submitted' THEN 'done' ELSE 'todo' END,
      '/personal-project/aura/sessions/' || s.id
    FROM aura_sessions s LEFT JOIN aura_reports r ON r.aura_session_id=s.id;
    """)
    sync = """
    UPDATE events SET
      status=(SELECT s.status FROM aura_calendar_state s WHERE s.event_id=events.id),
      completion_source='external',
      task_available_from=start_time,
      task_due_at=strftime('%Y-%m-%dT%H:%M:%SZ', start_time, '+3 days'),
      web_url=CASE WHEN web_url='' THEN
        (SELECT s.url FROM aura_calendar_state s WHERE s.event_id=events.id)
        ELSE web_url END
    WHERE id IN (SELECT event_id FROM aura_calendar_state);
    """
    for table in ('aura_clinic_rounds', 'aura_round_targets', 'aura_target_reports', 'aura_sessions', 'aura_reports'):
        for action in ('INSERT', 'UPDATE', 'DELETE'):
            db.executescript(f'CREATE TRIGGER IF NOT EXISTS calendar_sync_{table}_{action} AFTER {action} ON {table} BEGIN {sync} END;')
    db.executescript(f'CREATE TRIGGER IF NOT EXISTS calendar_sync_event_time AFTER UPDATE OF start_time,end_time ON events BEGIN {sync} END;')
    db.executescript(sync)
