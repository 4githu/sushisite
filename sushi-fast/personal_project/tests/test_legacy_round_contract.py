"""Synthetic SQLite regression contract for legacy Aura stages and templates."""
import os
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='aura-legacy-bootstrap-')) / 'bootstrap.sqlite'))

import pytest
from personal_project import db, repository as repo, schemas
from personal_project.db import connection

USER = 301
MID = 'grade1_semester1_midterm'
LEGACY = 'grade1_semester1'
FINAL = 'grade1_semester1_final'


@pytest.fixture(autouse=True)
def synthetic_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    db.init_db()


def school(user=USER):
    return repo.create_school(user, schemas.SchoolCreate(admission_year=2026, school_name='합성고'))


def create(school_id, number, stage, hour=9):
    return repo.create_clinic_round(USER, schemas.ClinicRoundCreate(
        school_id=school_id, round_number=number, progress_stage=stage,
        student_names=['합성 학생'], start_time=datetime.fromisoformat(f'2026-09-01T{hour:02d}:00:00+09:00'),
        end_time=datetime.fromisoformat(f'2026-09-01T{hour+1:02d}:00:00+09:00')))


def template(school_id, stage, label, number=1):
    return repo.save_round_template(USER, school_id, number, schemas.TemplateSave(
        progress_stage=stage, content_json={'blocks': [{'id': label, 'type': 'paragraph', 'children': [{'type': 'text', 'text': label}]}]}))


def report(item):
    return repo.get_or_create_target_report(USER, item['targets'][0]['id'])


def report_blocks(item):
    return [block['id'] for block in report(item)['contentJson']['blocks']]


def test_midterm_falls_back_to_active_legacy_template_but_final_is_isolated():
    s = school()
    template(s['id'], LEGACY, 'legacy-v1')
    active = template(s['id'], LEGACY, 'legacy-v2')
    mid = create(s['id'], 1, MID)
    final = create(s['id'], 1, FINAL, hour=11)
    before = report(mid)
    assert report_blocks(mid) == ['legacy-v2']
    assert before['templateVersion'] == active['version']
    assert report_blocks(final) != ['legacy-v2']
    template(s['id'], MID, 'new-midterm')
    second_mid = create(s['id'], 1, MID, hour=13)
    assert report_blocks(second_mid) == ['new-midterm']
    assert report_blocks(mid) == ['legacy-v2']  # existing snapshot is immutable
    template(s['id'], FINAL, 'final-only')
    second_final = create(s['id'], 1, FINAL, hour=15)
    assert report_blocks(second_final) == ['final-only']
    assert report_blocks(second_mid) == ['new-midterm']


def test_school_only_patch_preserves_legacy_stage_and_snapshot():
    original = school()
    other = repo.create_school(USER, schemas.SchoolCreate(admission_year=2026, school_name='다른 합성고'))
    template(original['id'], LEGACY, 'legacy')
    item = create(original['id'], 1, LEGACY)
    first = report(item)
    changed = repo.update_clinic_round(USER, item['id'], schemas.ClinicRoundUpdate(school_id=other['id']))
    assert changed['progressStage'] == LEGACY
    assert report(item)['id'] == first['id']
    assert report(item)['contentJson'] == first['contentJson']


def test_legacy_time_only_patch_keeps_stage_template_and_report_id():
    s = school()
    template(s['id'], LEGACY, 'legacy')
    item = create(s['id'], 1, LEGACY)
    first = report(item)
    updated = repo.update_clinic_round(USER, item['id'], schemas.ClinicRoundUpdate(
        start_time=datetime.fromisoformat('2026-09-01T09:30:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-01T10:30:00+09:00')))
    assert updated['progressStage'] == LEGACY
    assert report(item)['id'] == first['id']
    assert report(item)['contentJson'] == first['contentJson']
    assert report(item)['templateVersion'] == first['templateVersion']


@pytest.mark.parametrize('field,value', [('round_number', 1), ('progress_stage', LEGACY), ('round_numbers', [1])])
def test_unchanged_fields_do_not_delete_unedited_report(field, value):
    s = school()
    item = create(s['id'], 1, LEGACY)
    first = report(item)
    repo.update_clinic_round(USER, item['id'], schemas.ClinicRoundUpdate(**{field: value}))
    assert report(item)['id'] == first['id']


def test_following_unchanged_stage_and_first_number_keep_all_unedited_reports():
    s = school()
    items = repo.create_clinic_round_series(USER, schemas.ClinicRoundSeriesCreate(
        school_id=s['id'], round_number=1, progress_stage=LEGACY, student_names=['합성 학생'],
        start_time=datetime.fromisoformat('2026-09-01T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-01T10:00:00+09:00'), repeat_count=2))
    first_ids = [report(item)['id'] for item in items]
    repo.update_clinic_round(USER, items[0]['id'], schemas.ClinicRoundUpdate(
        scope='following', round_number=1, progress_stage=LEGACY))
    assert [report(item)['id'] for item in items] == first_ids


def test_distinct_midterm_and_final_numbers_can_start_at_one():
    s = school()
    legacy = create(s['id'], 1, LEGACY)
    mid = create(s['id'], 2, MID, hour=11)
    final = create(s['id'], 1, FINAL, hour=13)
    assert [(row['roundNumber'], row['progressStage']) for row in (legacy, mid, final)] == [
        (1, LEGACY), (2, MID), (1, FINAL)]


@pytest.mark.parametrize('legacy_stage', [
    'grade1_semester1', 'grade1_semester2', 'grade2_semester1',
    'grade2_semester2', 'grade3_semester1',
])
def test_each_midterm_alias_falls_back_only_when_legacy_template_active(legacy_stage):
    s = school()
    legacy_template = template(s['id'], legacy_stage, 'legacy-active')
    midterm_stage = f'{legacy_stage}_midterm'
    mid = create(s['id'], 1, midterm_stage)
    assert report_blocks(mid) == ['legacy-active']
    with connection() as conn:
        saved = conn.execute('SELECT template_id FROM aura_target_reports WHERE target_id = ?',
                             (mid['targets'][0]['id'],)).fetchone()
        assert saved['template_id'] == legacy_template['id']
        conn.execute('UPDATE aura_round_templates SET is_active = 0 WHERE id = ?', (legacy_template['id'],))
        conn.commit()
    next_mid = create(s['id'], 1, midterm_stage, hour=11)
    assert report_blocks(next_mid) != ['legacy-active']
    assert report_blocks(mid) == ['legacy-active']


def test_following_stage_change_recreates_only_unchanged_draft_on_changed_occurrences():
    s = school()
    items = repo.create_clinic_round_series(USER, schemas.ClinicRoundSeriesCreate(
        school_id=s['id'], round_number=1, progress_stage=LEGACY, student_names=['합성 학생'],
        start_time=datetime.fromisoformat('2026-09-01T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-01T10:00:00+09:00'), repeat_count=2))
    ids = [report(item)['id'] for item in items]
    repo.update_clinic_round(USER, items[0]['id'], schemas.ClinicRoundUpdate(
        scope='following', progress_stage=MID))
    assert [repo.get_clinic_round(USER, item['id'])['progressStage'] for item in items] == [MID, MID]
    assert [report(item)['id'] for item in items] != ids


def test_midterm_fallback_does_not_cross_school_or_round_number():
    a = school()
    b = repo.create_school(USER, schemas.SchoolCreate(admission_year=2026, school_name='독립 합성고'))
    template(a['id'], LEGACY, 'only-a-round-one')
    template(b['id'], LEGACY, 'only-b-round-two', number=2)
    assert report_blocks(create(b['id'], 1, MID)) != ['only-a-round-one']
    assert report_blocks(create(b['id'], 2, MID, hour=11)) == ['only-b-round-two']


def test_http_school_only_patch_and_time_only_patch_preserve_legacy_report():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from personal_project.router import current_user_id, router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user_id] = lambda: USER
    client = TestClient(app)
    a = school()
    b = repo.create_school(USER, schemas.SchoolCreate(admission_year=2026, school_name='이동 합성고'))
    item = create(a['id'], 1, LEGACY)
    before = report(item)
    path = f"/api/personal/aura/rounds/{item['id']}"
    moved = client.patch(path, json={'school_id': b['id']})
    assert moved.status_code == 200, moved.text
    assert moved.json()['progressStage'] == LEGACY
    timed = client.patch(path, json={
        'start_time': '2026-09-01T09:30:00+09:00',
        'end_time': '2026-09-01T10:30:00+09:00',
    })
    assert timed.status_code == 200, timed.text
    assert timed.json()['progressStage'] == LEGACY
    assert report(item)['id'] == before['id']
