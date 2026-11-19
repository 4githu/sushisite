"""Synthetic, isolated Aura target identity regression tests."""
import os
import tempfile
from pathlib import Path
os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='aura-identity-')) / 'bootstrap.sqlite'))

import pytest
from fastapi import HTTPException
from personal_project import db as project_db

from personal_project import repository as repo
from personal_project.db import connection
from personal_project.schemas import ClinicRoundCreate, ClinicRoundUpdate, SchoolCreate


@pytest.fixture(autouse=True)
def synthetic_db(tmp_path, monkeypatch):
    monkeypatch.setattr(project_db, 'DB_PATH', tmp_path / 'identity.sqlite')
    project_db.init_db()


def clinic(user=101):
    school = repo.create_school(user, SchoolCreate(admission_year=2026, school_name='합성고'))
    return repo.create_clinic_round(user, ClinicRoundCreate(
        school_id=school['id'], round_number=1, student_names=['가', '나'],
        start_time='2026-09-16T09:00:00+09:00', end_time='2026-09-16T10:00:00+09:00'))


def test_reorder_keeps_report_and_attachment_on_original_target():
    item = clinic()
    a, b = item['targets']
    report = repo.get_or_create_target_report(101, a['id'])
    with connection() as db:
        db.execute("UPDATE aura_target_reports SET content_json=?, generated_report_json=?, status='submitted' WHERE id=?",
                   ('{"owner":"A"}', '{"owner":"A"}', report['id']))
        db.execute("INSERT INTO aura_report_attachments (user_id,target_report_id,kind,mime_type,storage_name,byte_size) VALUES (101,?,'blank_test','image/png','synthetic-a.png',1)", (report['id'],))
        db.commit()
    changed = repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(targets=[
        {'id': b['id'], 'student_name': '나'}, {'id': a['id'], 'student_name': '가'}]))
    assert [t['id'] for t in changed['targets']] == [b['id'], a['id']]
    assert [t['studentName'] for t in changed['targets']] == ['나', '가']
    with connection() as db:
        row = db.execute('SELECT target_id, content_json, generated_report_json FROM aura_target_reports WHERE id=?', (report['id'],)).fetchone()
        attachment = db.execute('SELECT target_report_id FROM aura_report_attachments WHERE storage_name=?', ('synthetic-a.png',)).fetchone()
    assert tuple(row) == (a['id'], '{"owner":"A"}', '{"owner":"A"}')
    assert attachment[0] == report['id']


def test_name_swap_cannot_silently_relabel_ids_even_without_reports():
    item = clinic()
    a, b = item['targets']
    with pytest.raises(HTTPException) as error:
        repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(targets=[
            {'id': a['id'], 'student_name': '나'}, {'id': b['id'], 'student_name': '가'}]))
    assert error.value.status_code == 409
    assert [target['studentName'] for target in repo.get_clinic_round(101, item['id'])['targets']] == ['가', '나']


def test_add_and_remove_unreported_target_require_explicit_confirmation():
    item = clinic()
    a, b = item['targets']
    desired = [{'id': a['id'], 'student_name': '가'}, {'student_name': '다'}]
    with pytest.raises(HTTPException) as error:
        repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(targets=desired))
    assert error.value.status_code == 409
    assert [t['id'] for t in repo.get_clinic_round(101, item['id'])['targets']] == [a['id'], b['id']]
    changed = repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(targets=desired, confirm_target_removal=True))
    assert changed['targets'][0]['id'] == a['id']
    assert changed['targets'][1]['id'] != b['id']
    assert changed['targets'][1]['studentName'] == '다'


def test_reported_target_cannot_be_removed_even_with_confirmation():
    item = clinic()
    a, b = item['targets']
    report = repo.get_or_create_target_report(101, b['id'])
    with pytest.raises(HTTPException) as error:
        repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(targets=[{'id': a['id'], 'student_name': '가'}], confirm_target_removal=True))
    assert error.value.status_code == 409
    assert repo.get_or_create_target_report(101, b['id'])['id'] == report['id']


def test_rename_reported_target_requires_identity_confirmation():
    item = clinic()
    a, b = item['targets']
    report = repo.get_or_create_target_report(101, a['id'])
    desired = [{'id': a['id'], 'student_name': '가-개명'}, {'id': b['id'], 'student_name': '나'}]
    with pytest.raises(HTTPException) as error:
        repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(targets=desired))
    assert error.value.status_code == 409
    changed = repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(targets=desired, confirm_identity_rename=True))
    assert changed['targets'][0]['id'] == a['id']
    assert changed['targets'][0]['studentName'] == '가-개명'
    assert repo.get_or_create_target_report(101, a['id'])['id'] == report['id']


def test_legacy_name_only_update_and_foreign_target_are_rejected_atomically():
    item = clinic()
    foreign = clinic(202)
    a, b = item['targets']
    with pytest.raises(HTTPException) as legacy:
        repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(student_names=['나', '가']))
    assert legacy.value.status_code == 409
    with pytest.raises(HTTPException) as foreign_error:
        repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(targets=[
            {'id': foreign['targets'][0]['id'], 'student_name': '나'}, {'id': b['id'], 'student_name': '나'}], description='should rollback'))
    assert foreign_error.value.status_code in (404, 409)
    unchanged = repo.get_clinic_round(101, item['id'])
    assert [t['id'] for t in unchanged['targets']] == [a['id'], b['id']]
    assert unchanged['description'] == ''


def test_http_target_identity_boundary_and_delete_confirmation():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from personal_project.router import router, current_user_id
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user_id] = lambda: 101
    client = TestClient(app)
    own = clinic()
    other = clinic(202)
    path = f"/api/personal/aura/rounds/{own['id']}"
    assert client.patch(path, json={'student_names': ['나', '가']}).status_code == 409
    assert client.patch(path, json={'targets': [
        {'id': other['targets'][0]['id'], 'student_name': '침입'},
        {'id': own['targets'][1]['id'], 'student_name': '나'}]}).status_code == 409
    assert client.delete(f"/api/personal/aura/targets/{own['targets'][0]['id']}").status_code == 409
    assert client.delete(f"/api/personal/aura/targets/{own['targets'][0]['id']}?confirm=true").status_code == 204
    assert client.get(path).json()['targets'][0]['id'] == own['targets'][1]['id']
    app.dependency_overrides[current_user_id] = lambda: 202
    assert client.get(path).status_code == 404
    assert client.patch(path, json={'targets': [{'student_name': '침입'}]}).status_code == 404


def test_round_number_change_preserves_report_with_attachment_and_ai_payload():
    item = clinic()
    target = item['targets'][0]['id']
    report = repo.get_or_create_target_report(101, target)
    with connection() as db:
        db.execute("UPDATE aura_target_reports SET generated_report_json=?, status='submitted' WHERE id=?", ('{"owner":"A"}', report['id']))
        db.execute("INSERT INTO aura_report_attachments (user_id,target_report_id,kind,mime_type,storage_name,byte_size) VALUES (101,?,'blank_test','image/png','synthetic-a.png',1)", (report['id'],))
        db.commit()
    repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(round_number=2))
    with connection() as db:
        row = db.execute('SELECT target_id, generated_report_json FROM aura_target_reports WHERE id=?', (report['id'],)).fetchone()
        attachment = db.execute('SELECT target_report_id FROM aura_report_attachments WHERE storage_name=?', ('synthetic-a.png',)).fetchone()
    assert tuple(row) == (target, '{"owner":"A"}')
    assert attachment[0] == report['id']


def test_direct_target_delete_rejects_report_even_with_confirmation():
    item = clinic()
    target = item['targets'][0]['id']
    repo.get_or_create_target_report(101, target)
    with pytest.raises(HTTPException) as error:
        repo.delete_round_target(101, target, confirm=True)
    assert error.value.status_code == 409
    assert repo.get_clinic_round(101, item['id'])['targets'][0]['id'] == target


def test_following_target_edit_rejected_without_cross_round_identity_mapping():
    item = clinic()
    with pytest.raises(HTTPException) as error:
        repo.update_clinic_round(101, item['id'], ClinicRoundUpdate(scope='following', targets=[
            {'id': t['id'], 'student_name': t['studentName']} for t in item['targets']]))
    assert error.value.status_code == 409
