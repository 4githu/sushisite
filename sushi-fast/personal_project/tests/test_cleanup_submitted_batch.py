from personal_project import repository as repo
from personal_project.tests.test_report_attachment_lifecycle import setup, upload
from personal_project.cleanup_submitted_batch import cleanup_submitted


def test_removes_submitted_only_and_preserves_shared(setup):
    client, db, _, _, target, report, png = setup
    first = upload(client, target, png)
    second = upload(client, target, png)
    path1, _, _ = repo.read_target_report_attachment(101, first)
    path2, _, _ = repo.read_target_report_attachment(101, second)
    with repo.connection() as conn:
        conn.execute("UPDATE aura_target_reports SET status='submitted' WHERE id=?", (report,))
        # Emulate the pre-unique-index legacy database.
        conn.execute('ALTER TABLE aura_report_attachments RENAME TO old_atts')
        conn.execute('''CREATE TABLE aura_report_attachments (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, target_report_id INTEGER NOT NULL, kind TEXT NOT NULL, original_name TEXT NOT NULL, mime_type TEXT NOT NULL, storage_name TEXT NOT NULL, byte_size INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        conn.execute('INSERT INTO aura_report_attachments SELECT * FROM old_atts')
        conn.execute('DROP TABLE old_atts')
        row = conn.execute('SELECT * FROM aura_report_attachments WHERE id=?', (second,)).fetchone()
        conn.execute('INSERT INTO aura_report_attachments(user_id,target_report_id,kind,original_name,mime_type,storage_name,byte_size) VALUES(?,?,?,?,?,?,?)', (row['user_id'],row['target_report_id'],row['kind'],row['original_name'],row['mime_type'],row['storage_name'],row['byte_size']))
        conn.commit()
    result = cleanup_submitted()
    assert result['deleted'] == 1
    assert result['shared'] == 2
    assert not path1.exists()
    assert path2.exists()
    with repo.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM aura_report_attachments').fetchone()[0] == 2
