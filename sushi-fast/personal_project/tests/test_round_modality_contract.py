"""Synthetic-only round modality API and legacy migration contract."""
import os
import tempfile
from pathlib import Path

os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='aura-modality-bootstrap-')) / 'bootstrap.sqlite'))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import db
from personal_project.db import connection
from personal_project.router import current_user_id, router

USER = 9193
OTHER = 9194


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    db.init_db()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user_id] = lambda: USER
    return TestClient(app), app


def school(client, name='대전', year=2027):
    response = client.post('/api/personal/aura/schools', json={'admission_year': year, 'school_name': name})
    assert response.status_code == 201, response.text
    return response.json()


def payload(school_id, **extra):
    return {'school_id': school_id, 'round_number': 1, 'student_names': ['동명이인'],
            'start_time': '2026-11-05T09:00:00+09:00', 'end_time': '2026-11-05T10:00:00+09:00',
            'description': 'Zoom 비대면 메모', **extra}


def test_post_get_patch_roundtrip_keeps_memo_independent(api):
    client, _ = api
    sid = school(client)['id']
    created = client.post('/api/personal/aura/rounds', json=payload(sid, modality='in_person'))
    assert created.status_code == 201, created.text
    rid = created.json()['id']
    assert created.json()['modality'] == 'in_person'
    assert client.get(f'/api/personal/aura/rounds/{rid}').json()['modality'] == 'in_person'
    assert client.get('/api/personal/aura/rounds').json()[0]['modality'] == 'in_person'
    patch = client.patch(f'/api/personal/aura/rounds/{rid}', json={'modality': 'remote'})
    assert patch.status_code == 200, patch.text
    assert patch.json()['modality'] == 'remote'
    assert patch.json()['description'] == 'Zoom 비대면 메모'
    assert client.get(f'/api/personal/aura/rounds/{rid}').json()['modality'] == 'remote'
    with connection() as conn:
        assert conn.execute('SELECT modality FROM aura_clinic_rounds WHERE id=?', (rid,)).fetchone()[0] == 'remote'


def test_new_round_defaults_to_in_person_and_invalid_modes_are_rejected(api):
    client, _ = api
    sid = school(client)['id']
    created = client.post('/api/personal/aura/rounds', json=payload(sid))
    assert created.status_code == 201
    rid = created.json()['id']
    assert created.json()['modality'] == 'in_person'
    for bad in ('online', '대면', None, True):
        assert client.patch(f'/api/personal/aura/rounds/{rid}', json={'modality': bad}).status_code == 422
        assert client.post('/api/personal/aura/rounds', json=payload(sid, modality=bad)).status_code == 422
    assert client.get(f'/api/personal/aura/rounds/{rid}').json()['modality'] == 'in_person'


def test_series_following_only_same_owner_group_and_requery(api):
    client, app = api
    sid = school(client)['id']
    series = client.post('/api/personal/aura/rounds/series', json={**payload(sid, modality='remote'), 'repeat_count': 3})
    assert series.status_code == 201, series.text
    ids = [item['id'] for item in series.json()]
    assert [item['modality'] for item in series.json()] == ['remote'] * 3
    other_school = school(client, '대전합성')['id']
    another = client.post('/api/personal/aura/rounds', json=payload(other_school, modality='in_person', allow_overlap=True)).json()
    app.dependency_overrides[current_user_id] = lambda: OTHER
    foreign_school = school(client, '대전', 2027)['id']
    foreign = client.post('/api/personal/aura/rounds', json=payload(foreign_school, modality='in_person', allow_overlap=True)).json()
    assert client.patch(f'/api/personal/aura/rounds/{ids[1]}', json={'modality': 'in_person', 'scope': 'following'}).status_code == 404
    assert client.get(f'/api/personal/aura/rounds/{ids[1]}/modality-preview?scope=following').status_code == 404
    app.dependency_overrides[current_user_id] = lambda: USER
    preview = client.get(f'/api/personal/aura/rounds/{ids[1]}/modality-preview?scope=following')
    assert preview.status_code == 200, preview.text
    assert [row['id'] for row in preview.json()['rounds']] == ids[1:]
    assert all(row['modality'] == 'remote' for row in preview.json()['rounds'])
    assert client.patch(f'/api/personal/aura/rounds/{ids[1]}', json={'modality': 'in_person', 'scope': 'following'}).status_code == 409
    assert client.patch(f'/api/personal/aura/rounds/{ids[1]}', json={'modality': 'in_person', 'scope': 'following', 'expected_round_ids': ids[1:2]}).status_code == 409
    update = client.patch(f'/api/personal/aura/rounds/{ids[1]}', json={'modality': 'in_person', 'scope': 'following', 'expected_round_ids': ids[1:], 'expected_round_state': preview.json()['roundState']})
    assert update.status_code == 200, update.text
    assert update.json()['affectedRoundIds'] == ids[1:]
    assert [client.get(f'/api/personal/aura/rounds/{rid}').json()['modality'] for rid in ids] == ['remote', 'in_person', 'in_person']
    assert client.get(f'/api/personal/aura/rounds/{another["id"]}').json()['modality'] == 'in_person'
    assert client.get(f'/api/personal/aura/rounds/{foreign["id"]}').status_code == 404
    app.dependency_overrides[current_user_id] = lambda: OTHER
    assert client.get(f'/api/personal/aura/rounds/{foreign["id"]}').json()['modality'] == 'in_person'


@pytest.mark.parametrize('change', ['modality', 'time', 'target'])
def test_following_same_ids_changed_content_requires_repreview(api, change):
    client, _ = api
    sid = school(client)['id']
    series = client.post('/api/personal/aura/rounds/series', json={**payload(sid, modality='remote'), 'repeat_count': 3}).json()
    ids = [row['id'] for row in series]
    url = f'/api/personal/aura/rounds/{ids[1]}'
    preview = client.get(f'{url}/modality-preview?scope=following').json()
    stale = {'scope': 'following', 'modality': 'in_person',
             'expected_round_ids': ids[1:], 'expected_round_state': preview['roundState']}
    changed_id = ids[2]
    if change == 'modality':
        response = client.patch(f'/api/personal/aura/rounds/{changed_id}', json={'modality': 'unverified'})
    elif change == 'time':
        response = client.patch(f'/api/personal/aura/rounds/{changed_id}', json={
            'start_time': '2026-11-19T11:00:00+09:00',
            'end_time': '2026-11-19T12:00:00+09:00'})
    else:
        target = series[2]['targets'][0]
        response = client.patch(f'/api/personal/aura/rounds/{changed_id}', json={
            'targets': [{'id': target['id'], 'student_name': '변경된 학생'}],
            'confirm_identity_rename': True})
    assert response.status_code == 200, response.text
    assert client.patch(url, json=stale).status_code == 409
    assert client.get(f'/api/personal/aura/rounds/{changed_id}').json()['modality'] != 'in_person'
    assert client.get(url).json()['modality'] == 'remote'
    fresh = client.get(f'{url}/modality-preview?scope=following').json()
    assert fresh['roundState'] != preview['roundState']
    assert client.patch(url, json={**stale, 'expected_round_state': fresh['roundState']}).status_code == 200


def test_following_ids_alone_cannot_bypass_content_guard(api):
    client, _ = api
    sid = school(client)['id']
    rounds = client.post('/api/personal/aura/rounds/series', json={**payload(sid), 'repeat_count': 2}).json()
    ids = [row['id'] for row in rounds]
    url = f'/api/personal/aura/rounds/{ids[0]}'
    assert client.patch(url, json={'scope': 'following', 'modality': 'remote', 'expected_round_ids': ids}).status_code == 409
    assert [client.get(f'/api/personal/aura/rounds/{rid}').json()['modality'] for rid in ids] == ['in_person'] * 2


def test_existing_rounds_migrate_to_unverified_without_name_inference(api, monkeypatch):
    client, _ = api
    sid = school(client)['id']
    rid = client.post('/api/personal/aura/rounds', json=payload(sid)).json()['id']
    with connection() as conn:
        conn.execute('ALTER TABLE aura_clinic_rounds DROP COLUMN modality')
        conn.commit()
    db.init_db()
    assert client.get(f'/api/personal/aura/rounds/{rid}').json()['modality'] == 'unverified'
    with connection() as conn:
        assert conn.execute('SELECT modality FROM aura_clinic_rounds WHERE id=?', (rid,)).fetchone()[0] == 'unverified'
    db.init_db()
    assert client.get(f'/api/personal/aura/rounds/{rid}').json()['modality'] == 'unverified'
    assert client.patch(f'/api/personal/aura/rounds/{rid}', json={'modality': 'remote'}).status_code == 200
    db.init_db()
    assert client.get(f'/api/personal/aura/rounds/{rid}').json()['modality'] == 'remote'

@pytest.mark.parametrize('paid', [False, True])
def test_same_price_time_shift_with_snapshot_ignores_nonoverlapping_utc_event(api, paid):
    from datetime import datetime
    client, _ = api
    sid = school(client)['id']
    created = client.post('/api/personal/aura/rounds', json=payload(sid,
        progress_stage='grade1_semester1_midterm',
        start_time='2026-11-08T10:00:00+09:00', end_time='2026-11-08T11:00:00+09:00')).json()
    rid = created['id']
    with connection() as conn:
        conn.execute("INSERT INTO events(user_id,title,start_time,end_time,type) VALUES (?,?,?,?,?)",
            (USER,'Synthetic evening class','2026-11-08T09:00:00+00:00','2026-11-08T10:00:00+00:00','aura'))
        conn.execute("UPDATE aura_clinic_rounds SET payment_status=? WHERE id=?", ('paid' if paid else 'pending',rid))
        conn.execute("INSERT INTO aura_settlement_snapshots(user_id,year,month,data_json,pricing_version) VALUES(?,?,?,?,?)",(USER,2026,11,'{"items":[],"totalAmount":30000}',6))
        conn.commit()
    url=f'/api/personal/aura/rounds/{rid}'
    preview=client.get(f'{url}/modality-preview?scope=following').json()
    result=client.patch(url,json={'start_time':'2026-11-08T09:30:00+09:00',
        'end_time':'2026-11-08T10:30:00+09:00','modality':'remote','scope':'following',
        'expected_round_ids':[r['id'] for r in preview['rounds']], 'expected_round_state':preview['roundState']})
    assert result.status_code == 200, result.text
    saved=client.get(url).json()
    assert datetime.fromisoformat(saved['startTime']) == datetime.fromisoformat('2026-11-08T09:30:00+09:00')
    assert saved['modality']=='remote' and saved['amount']==created['amount']
    assert saved['paymentStatus']==('paid' if paid else 'pending')
    assert [t['id'] for t in saved['targets']]==[t['id'] for t in created['targets']]
    with connection() as conn:
        assert conn.execute('SELECT data_json FROM aura_settlement_snapshots WHERE user_id=?',(USER,)).fetchone()[0]=='{"items":[],"totalAmount":30000}'


@pytest.mark.parametrize('existing_start,existing_end',[
    ('2026-11-08T01:00:00+00:00','2026-11-08T02:00:00+00:00'),
    ('2026-11-08T10:00:00','2026-11-08T11:00:00'),
])
def test_intended_overlap_is_allowed_for_utc_and_legacy_seoul_wall_times(api,existing_start,existing_end):
    client,_=api
    sid=school(client)['id']
    created=client.post('/api/personal/aura/rounds',json=payload(sid,
        start_time='2026-11-08T08:00:00+09:00',end_time='2026-11-08T09:00:00+09:00')).json()
    with connection() as conn:
        conn.execute("INSERT INTO events(user_id,title,start_time,end_time,type) VALUES (?,?,?,?,?)",
            (USER,'Synthetic overlap',existing_start,existing_end,'aura'));conn.commit()
    response=client.patch(f"/api/personal/aura/rounds/{created['id']}",json={
        'start_time':'2026-11-08T09:30:00+09:00','end_time':'2026-11-08T10:30:00+09:00'})
    assert response.status_code==200,response.text
    assert client.get(f"/api/personal/aura/rounds/{created['id']}").json()['startTime'].startswith('2026-11-08T09:30:00')
