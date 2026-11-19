"""Additional completion safety checks using only the isolated test fixture."""
from personal_project import db, repository as repo
from personal_project.tests.test_report_attachment_lifecycle import setup, upload


def test_other_user_cannot_complete_or_remove_image(setup):
    client, app, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    from personal_project.router import current_user_id
    app.dependency_overrides[current_user_id] = lambda: 202
    assert client.post(f'/api/personal/aura/target-reports/{report}/submit').status_code == 404
    assert path.read_bytes() == png
    with db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM aura_attachment_cleanup_journal').fetchone()[0] == 0


def test_failure_to_verify_candidate_never_unlinks_file(setup, monkeypatch):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    monkeypatch.setattr(repo.attachment_cleanup, 'snapshot', lambda *args: None)
    response = client.post(f'/api/personal/aura/target-reports/{report}/submit')
    assert response.status_code == 500
    assert path.read_bytes() == png
    with db.connection() as conn:
        row = conn.execute('SELECT status, file_sha256 FROM aura_attachment_cleanup_journal').fetchone()
        assert tuple(row) == ('pending', None)
