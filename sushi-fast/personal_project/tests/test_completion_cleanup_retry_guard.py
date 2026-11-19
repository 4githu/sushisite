"""An unverified pending cleanup must not be reported as complete."""
from personal_project import db, repository as repo
from personal_project.tests.test_report_attachment_lifecycle import setup, upload


def test_unverified_cleanup_stays_pending_on_submit_retry(setup, monkeypatch):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    monkeypatch.setattr(repo.attachment_cleanup, 'snapshot', lambda *args: None)
    url = f'/api/personal/aura/target-reports/{report}/submit'
    assert client.post(url).status_code == 500
    assert client.post(url).status_code == 500
    assert path.read_bytes() == png
    with db.connection() as conn:
        assert conn.execute("SELECT count(*) FROM aura_attachment_cleanup_journal WHERE status='pending'").fetchone()[0] == 1
