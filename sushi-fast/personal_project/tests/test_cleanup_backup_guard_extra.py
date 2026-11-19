from personal_project import repository as repo
from personal_project.cleanup_submitted_batch import cleanup_submitted
from personal_project.tests.test_report_attachment_lifecycle import setup, upload

def test_absent_backup_blocks_deletion(setup):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    with repo.connection() as conn:
        conn.execute("UPDATE aura_target_reports SET status='submitted' WHERE id=?", (report,))
        conn.commit()
    result = cleanup_submitted(expected_backups={})
    assert result['backup_mismatch'] == 1
    assert path.exists()
    with repo.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM aura_report_attachments WHERE id=?', (attachment,)).fetchone()[0] == 1
