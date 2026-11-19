"""Synthetic characterization of Aura round/identity safety boundaries."""
import os
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='aura-room-bootstrap-')) / 'bootstrap.sqlite'))

import pytest
from personal_project import db, repository as repo, schemas
from personal_project.academic import canonical_school_name, parse_legacy_school_name

USER = 9191


@pytest.fixture(autouse=True)
def synthetic_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    db.init_db()


def school(year, name):
    return repo.create_school(USER, schemas.SchoolCreate(admission_year=year, school_name=name))


def round_(parent, number, hour, description):
    return repo.create_clinic_round(USER, schemas.ClinicRoundCreate(
        school_id=parent['id'], round_number=number, student_names=['최우진'],
        start_time=datetime.fromisoformat(f'2026-10-29T{hour:02d}:00:00+09:00'),
        end_time=datetime.fromisoformat(f'2026-10-29T{hour+1:02d}:00:00+09:00'),
        description=description,
    ))


def test_synthetic_rounds_do_not_infer_modality_from_description():
    parent = school(2027, '대전')
    remote_like = round_(parent, 1, 9, 'Zoom 링크 전달')
    in_person_with_remote_word = round_(parent, 2, 12, '비대면 상담 준비 후 대면 진행')
    for row in (remote_like, in_person_with_remote_word):
        response = repo.get_clinic_round(USER, row['id'])
        assert response['description']
        assert response['modality'] == 'in_person'
        assert 'isRemote' not in response
    assert 'modality' in schemas.ClinicRoundCreate.model_fields
    assert 'modality' in schemas.ClinicRoundUpdate.model_fields


def test_same_student_name_does_not_identify_a_school_or_target():
    first = round_(school(2027, '대전'), 1, 9, '')
    second = round_(school(2026, '합성고'), 1, 12, '')
    assert first['targets'][0]['studentName'] == second['targets'][0]['studentName']
    assert first['schoolId'] != second['schoolId']
    assert first['targets'][0]['id'] != second['targets'][0]['id']
    assert first['id'] != second['id']


def test_school_code_must_be_resolved_to_a_unique_school_id():
    first = school(2027, '대전')
    second = school(2027, '대전합성')
    assert first['name'] == canonical_school_name(2027, '대전') == '27대전'
    assert parse_legacy_school_name('대전27')[1] == '대전'
    assert first['id'] != second['id']
    assert second['name'].startswith(first['name'])
