"""Synthetic SQLite/filesystem only: completion cleanup safety."""
from personal_project import db, repository as repo, router
from personal_project.schemas import SchoolCreate, ClinicRoundCreate
from datetime import datetime
from personal_project.tests.test_report_attachment_lifecycle import setup, upload
import pytest


def test_manual_completion_cleans_only_owned_unshared_image(setup):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    response = client.post(f'/api/personal/aura/target-reports/{report}/submit')
    assert response.status_code == 200, response.text
    assert not path.exists()
    assert client.get(f'/api/personal/aura/targets/{target}/attachments').json() == []
    with db.connection() as conn:
        journal = conn.execute('SELECT reason, status FROM aura_attachment_cleanup_journal').fetchone()
        assert tuple(journal) == ('attachment', 'completed')


def test_shared_storage_name_is_retained(setup):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    with db.connection() as conn:
        # Simulate a legacy database lacking the current UNIQUE constraint.
        conn.execute('CREATE TABLE legacy_attachments AS SELECT * FROM aura_report_attachments')
        conn.execute('DROP TABLE aura_report_attachments')
        conn.execute('ALTER TABLE legacy_attachments RENAME TO aura_report_attachments')
        row = conn.execute('SELECT * FROM aura_report_attachments WHERE id=?', (attachment,)).fetchone()
        conn.execute('INSERT INTO aura_report_attachments (user_id,target_report_id,kind,original_name,mime_type,storage_name,byte_size) VALUES (?,?,?,?,?,?,?)', (row['user_id'], row['target_report_id'], row['kind'], 'shared.png', row['mime_type'], row['storage_name'], row['byte_size']))
        conn.commit()
    response = client.post(f'/api/personal/aura/target-reports/{report}/submit')
    assert response.status_code == 200, response.text
    assert path.read_bytes() == png
    assert len(client.get(f'/api/personal/aura/targets/{target}/attachments').json()) == 2


@pytest.mark.parametrize('result', [{'sent': False}, {'sent': True, 'deliveryStatus': 'unknown'}, {'sent': True, 'deliveryStatus': 'partial'}])
def test_unverified_delivery_keeps_attachment(setup, result):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    with pytest.raises(router.HTTPException):
        router._complete_verified_clinic_delivery(result, 101, report)
    assert path.read_bytes() == png
    assert client.get(f'/api/personal/aura/targets/{target}/report').json()['status'] != 'submitted'


def test_verified_delivery_cleans_attachment(setup):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    router._complete_verified_clinic_delivery({'sent': True, 'deliveryStatus': 'verified'}, 101, report)
    assert not path.exists()
    assert client.get(f'/api/personal/aura/targets/{target}/report').json()['status'] == 'submitted'


def test_http_unknown_preserves_image_until_verified_new_request(setup, monkeypatch):
    client, app, _, _, target, report, png = setup
    app.dependency_overrides[router.native_kakao_user_id] = lambda: 101
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    monkeypatch.setattr(router.native_kakao, 'create_clinic_job', lambda *_: {'jobId': 'synthetic', 'deliveryFormat': 'images'})
    monkeypatch.setattr(router.native_kakao, 'discard_clinic_job', lambda *_: None)
    monkeypatch.setattr(router.native_kakao, 'store_page', lambda *_: None)
    monkeypatch.setattr(router.report_pdf, 'render_pages', lambda *a, **kw: [b'synthetic-page'])
    result = {'sent': False, 'deliveryStatus': 'unknown'}
    monkeypatch.setattr(router.native_kakao, 'send_clinic_job', lambda *_: result)
    endpoint = f'/api/personal/aura/targets/{target}/kakao-clinic/send-report'
    headers = {'origin': 'https://aura.chobab.app'}
    assert client.post(endpoint, headers=headers).status_code == 409
    assert path.read_bytes() == png
    result.update(sent=True, deliveryStatus='verified')
    assert client.post(endpoint, headers=headers).status_code == 200
    assert not path.exists()


def test_http_verified_send_cleans_image(setup, monkeypatch):
    client, app, _, _, target, report, png = setup
    app.dependency_overrides[router.native_kakao_user_id] = lambda: 101
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    monkeypatch.setattr(router.native_kakao, 'create_clinic_job', lambda *_: {'jobId': 'synthetic', 'deliveryFormat': 'images'})
    monkeypatch.setattr(router.native_kakao, 'discard_clinic_job', lambda *_: None)
    monkeypatch.setattr(router.native_kakao, 'store_page', lambda *_: None)
    monkeypatch.setattr(router.report_pdf, 'render_pages', lambda *a, **kw: [b'synthetic-page'])
    monkeypatch.setattr(router.native_kakao, 'send_clinic_job', lambda *_: {'sent': True, 'deliveryStatus': 'verified'})
    endpoint = f'/api/personal/aura/targets/{target}/kakao-clinic/send-report'
    assert client.post(endpoint, headers={'origin': 'https://aura.chobab.app'}).status_code == 200
    assert not path.exists()


def test_completion_preserves_other_owner(setup):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    school = repo.create_school(202, SchoolCreate(admission_year=2026, school_name='가상학교2'))
    session = repo.create_clinic_round(202, ClinicRoundCreate(
        school_id=school['id'], round_number=1, student_names=['가상학생2'],
        start_time=datetime.fromisoformat('2026-09-16T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-16T10:00:00+09:00')))
    other = repo.save_target_report_attachment(202, session['targets'][0]['id'], 'blank_test', 'x.png', 'image/png', png)
    other_path, _, _ = repo.read_target_report_attachment(202, other['id'])
    assert client.post(f'/api/personal/aura/target-reports/{report}/submit').status_code == 200
    assert not path.exists()
    assert other_path.read_bytes() == png


def test_postcommit_cleanup_failure_retains_pending_journal(setup, monkeypatch):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    def fail(_):
        raise router.HTTPException(status_code=500, detail='synthetic cleanup failure')
    monkeypatch.setattr(repo, '_remove_attachment_files', fail)
    assert client.post(f'/api/personal/aura/target-reports/{report}/submit').status_code == 500
    assert path.read_bytes() == png
    assert client.get(f'/api/personal/aura/targets/{target}/report').json()['status'] == 'submitted'
    with db.connection() as conn:
        assert conn.execute('SELECT status FROM aura_attachment_cleanup_journal').fetchone()[0] == 'pending'
