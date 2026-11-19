"""Loopback-only synthetic Aura API for browser integration; never import the production app."""
import os
from pathlib import Path

path = os.environ.get('PERSONAL_PROJECT_DB_PATH')
if not path or os.environ.get('AURA_INTEGRATION_ROOT') is None:
    raise RuntimeError('Explicit isolated database and integration root are required')
root = Path(os.environ['AURA_INTEGRATION_ROOT']).resolve()
if not Path(path).resolve().is_relative_to(root) or not root.name.startswith('aura-integration-'):
    raise RuntimeError('Refusing non-test database path')

from fastapi import FastAPI
from personal_project import db, repository as repo, schemas
from personal_project.router import router, current_user_id

repo.ATTACHMENT_ROOT = root / 'attachments'
app = FastAPI()
app.include_router(router)
app.dependency_overrides[current_user_id] = lambda: 301  # synthetic identity, no login or credentials


@app.get('/auth/isjwt')
def synthetic_identity():
    return {'sub': '301', 'data': {'id': '301', 'name': '합성 계정', 'email': 'synthetic.invalid'}, 'exp': 9999999999}


@app.post('/__test/seed')
def seed():
    marker = root / 'seeded'
    if marker.exists():
        raise RuntimeError('Fresh database required for integration seed')
    db.init_db()
    marker.touch()
    school = repo.create_school(301, schemas.SchoolCreate(admission_year=2026, school_name='합성검증고'))
    other = repo.create_school(301, schemas.SchoolCreate(admission_year=2026, school_name='합성이동고'))
    for number in (1, 3):
        repo.save_round_template(301, school['id'], number, schemas.TemplateSave(progress_stage='grade1_semester1', content_json={
            'blocks': [{'id': 'legacy-template', 'type': 'paragraph', 'children': [{'type': 'text', 'text': 'legacy'}]}]}))
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo('Asia/Seoul')).replace(hour=16, minute=0, second=0, microsecond=0)
    for n in (1, 2):
        # First round mirrors pre-timezone legacy storage; second stays aware.
        start = today + timedelta(hours=n - 1)
        end = today + timedelta(hours=n)
        if n == 1:
            start, end = start.replace(tzinfo=None), end.replace(tzinfo=None)
        repo.create_clinic_round(301, schemas.ClinicRoundCreate(
            school_id=school['id'], round_number=n, progress_stage='grade1_semester1',
            student_names=['합성 학생'], start_time=start, end_time=end))
    return {'school': school['id'], 'other': other['id']}


@app.post('/__test/classroom-tick')
def classroom_tick():
    """Isolated, mock-only outbox boundary for the real-browser/API integration test."""
    import sqlite3
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from personal_project import aura_classroom_outbox as outbox
    from personal_project.aura_classroom_input import read_owner_rounds

    conn = sqlite3.connect(root / 'classroom-outbox.sqlite')
    conn.row_factory = sqlite3.Row
    outbox.init(conn)
    calls = []

    def mock_bridge(command, **kwargs):
        calls.append({'command': command, **kwargs})
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        return {'sent': True}

    now = datetime.now(ZoneInfo('Asia/Seoul')).replace(hour=13, minute=0, second=0, microsecond=0)
    result = outbox.tick(conn, 301, now, lambda owner: read_owner_rounds(owner, now), mock_bridge, approved=True)
    conn.close()
    return {'result': result, 'calls': calls}
