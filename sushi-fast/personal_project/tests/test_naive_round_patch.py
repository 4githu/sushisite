"""Legacy timezone-free Aura events are Seoul wall times, not host-local/UTC."""
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import db, repository as repo, schemas
from personal_project.db import connection
from personal_project.router import current_user_id, router

USER = 301


def test_naive_legacy_round_time_patch_uses_seoul_wall_time_and_keeps_report(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    db.init_db()
    school = repo.create_school(USER, schemas.SchoolCreate(admission_year=2026, school_name='합성고'))
    item = repo.create_clinic_round(USER, schemas.ClinicRoundCreate(
        school_id=school['id'], round_number=1, progress_stage='grade1_semester1',
        student_names=['합성 학생'], start_time=datetime.fromisoformat('2026-11-03T16:00:00'),
        end_time=datetime.fromisoformat('2026-11-03T17:00:00')))
    report = repo.get_or_create_target_report(USER, item['targets'][0]['id'])
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user_id] = lambda: USER
    client = TestClient(app)
    response = client.patch(f"/api/personal/aura/rounds/{item['id']}", json={
        'start_time': '2026-11-03T17:00:00+09:00',
        'end_time': '2026-11-03T18:00:00+09:00',
    })
    assert response.status_code == 200, response.text
    assert response.json()['startTime'] == '2026-11-03T17:00:00+09:00'
    assert response.json()['endTime'] == '2026-11-03T18:00:00+09:00'
    assert repo.get_or_create_target_report(USER, item['targets'][0]['id'])['id'] == report['id']
    with connection() as conn:
        event = conn.execute('SELECT start_time, end_time FROM events WHERE id = ?',
                             (item['eventId'],)).fetchone()
    assert event['start_time'] == '2026-11-03T17:00:00+09:00'
    assert event['end_time'] == '2026-11-03T18:00:00+09:00'


def test_naive_legacy_end_only_patch_normalizes_untouched_start(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    db.init_db()
    school = repo.create_school(USER, schemas.SchoolCreate(admission_year=2026, school_name='합성고'))
    item = repo.create_clinic_round(USER, schemas.ClinicRoundCreate(
        school_id=school['id'], round_number=1, progress_stage='grade1_semester1',
        student_names=['합성 학생'], start_time=datetime.fromisoformat('2026-11-03T16:00:00'),
        end_time=datetime.fromisoformat('2026-11-03T17:00:00')))
    updated = repo.update_clinic_round(USER, item['id'], schemas.ClinicRoundUpdate(
        end_time=datetime.fromisoformat('2026-11-03T09:00:00+00:00')))
    assert updated['startTime'] == '2026-11-03T16:00:00+09:00'
    assert updated['endTime'] == '2026-11-03T18:00:00+09:00'
    assert updated['amount'] == item['amount'] * 2
