import pytest
from personal_project import db, repository as repo
from personal_project.tests.test_report_attachment_lifecycle import setup, upload


def test_patch_submitted_cleans_image(setup):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    response = client.patch(f'/api/personal/aura/target-reports/{report}', json={'status': 'submitted'})
    assert response.status_code == 200
    assert not path.exists()


def test_submit_retries_pending_cleanup_without_resending(setup, monkeypatch):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    original = repo._remove_attachment_files
    monkeypatch.setattr(repo, '_remove_attachment_files', lambda _: (_ for _ in ()).throw(RuntimeError('test')))
    with pytest.raises(RuntimeError):
        client.post(f'/api/personal/aura/target-reports/{report}/submit')
    assert path.exists()
    monkeypatch.setattr(repo, '_remove_attachment_files', original)
    assert client.post(f'/api/personal/aura/target-reports/{report}/submit').status_code == 200
    assert not path.exists()
    with db.connection() as conn:
        assert conn.execute("SELECT count(*) FROM aura_attachment_cleanup_journal WHERE status='pending'").fetchone()[0] == 0
