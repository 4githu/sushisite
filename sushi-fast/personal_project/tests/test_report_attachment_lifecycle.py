"""Synthetic-only Aura report image lifetime and PDF HTTP regressions."""
import os
import tempfile
from datetime import datetime
from pathlib import Path

os.environ.setdefault('PERSONAL_PROJECT_DB_PATH', str(Path(tempfile.mkdtemp(prefix='aura-pdf-life-')) / 'bootstrap.sqlite'))

import fitz
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personal_project import db as project_db, repository as repo
from personal_project.router import current_user_id, router
from personal_project.schemas import ClinicRoundCreate, SchoolCreate


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(project_db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    monkeypatch.setattr(repo, 'ATTACHMENT_ROOT', tmp_path / 'images')
    project_db.init_db()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_user_id] = lambda: 101
    client = TestClient(app)
    school = repo.create_school(101, SchoolCreate(admission_year=2026, school_name='가상학교'))
    session = repo.create_clinic_round(101, ClinicRoundCreate(
        school_id=school['id'], round_number=1, student_names=['합성 학생'],
        start_time=datetime.fromisoformat('2026-09-16T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-16T10:00:00+09:00')))
    target = session['targets'][0]['id']
    report = repo.get_or_create_target_report(101, target)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 24, 24), False)
    png = pix.tobytes('png')
    return client, app, school['id'], session['id'], target, report['id'], png


def upload(client, target, png):
    response = client.post(f'/api/personal/aura/targets/{target}/attachments?kind=blank_test&filename=test.png',
                           content=png, headers={'content-type': 'image/png'})
    assert response.status_code == 201, response.text
    return response.json()['id']


def image_count(response):
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'private, no-store'
    with fitz.open(stream=response.content, filetype='pdf') as pdf:
        return sum(len(page.get_images(full=True)) for page in pdf)


def test_submitted_report_redownload_omits_cleaned_image_and_keeps_owner_boundary(setup):
    client, app, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    pdf_path = f'/api/personal/aura/targets/{target}/report.pdf'
    before = client.get(pdf_path)
    assert image_count(before) >= 1
    assert client.post(f'/api/personal/aura/target-reports/{report}/submit').status_code == 200
    assert not path.exists()
    assert client.get(f'/api/personal/aura/targets/{target}/attachments').json() == []
    assert client.get(f'/api/personal/aura/report-attachments/{attachment}').status_code == 404
    assert image_count(client.get(pdf_path)) == 0
    assert image_count(client.get(pdf_path)) == 0
    app.dependency_overrides[current_user_id] = lambda: 202
    assert client.get(pdf_path).status_code == 404
    assert client.get(f'/api/personal/aura/report-attachments/{attachment}').status_code == 404
    assert client.delete(f'/api/personal/aura/report-attachments/{attachment}').status_code == 404
    assert not path.exists()


def test_explicit_draft_attachment_deletion_removes_file_and_regenerated_pdf(setup):
    client, _, _, _, target, _, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    assert image_count(client.get(f'/api/personal/aura/targets/{target}/report.pdf')) >= 1
    assert client.delete(f'/api/personal/aura/report-attachments/{attachment}').status_code == 204
    assert not path.exists()
    assert not path.parent.exists()
    assert client.get(f'/api/personal/aura/report-attachments/{attachment}').status_code == 404
    assert client.get(f'/api/personal/aura/targets/{target}/attachments').json() == []
    assert image_count(client.get(f'/api/personal/aura/targets/{target}/report.pdf')) == 0


def test_submitted_attachment_cannot_be_deleted_without_reopening_report(setup):
    client, _, _, _, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    assert client.post(f'/api/personal/aura/target-reports/{report}/submit').status_code == 200
    assert client.delete(f'/api/personal/aura/report-attachments/{attachment}').status_code == 404
    assert not path.exists()
    assert image_count(client.get(f'/api/personal/aura/targets/{target}/report.pdf')) == 0
    refused = client.post(f'/api/personal/aura/targets/{target}/attachments?kind=blank_test&filename=late.png',
                          content=png, headers={'content-type': 'image/png'})
    assert refused.status_code == 409
    assert not path.parent.exists() or list(path.parent.iterdir()) == []


@pytest.mark.parametrize('delete_level', ['round', 'school'])
def test_parent_deletion_cleans_submitted_attachment_files(setup, delete_level):
    client, _, school, session, target, report, png = setup
    attachment = upload(client, target, png)
    path, _, _ = repo.read_target_report_attachment(101, attachment)
    assert client.post(f'/api/personal/aura/target-reports/{report}/submit').status_code == 200
    endpoint = (f'/api/personal/aura/rounds/{session}' if delete_level == 'round'
                else f'/api/personal/aura/schools/{school}')
    assert client.delete(endpoint).status_code == 204
    assert not path.exists()
    assert not path.parent.exists()
    assert client.get(f'/api/personal/aura/report-attachments/{attachment}').status_code == 404
    assert client.get(f'/api/personal/aura/targets/{target}/report.pdf').status_code == 404


def test_round_deletion_does_not_remove_other_owners_files(setup):
    client, _, _, session, target, _, png = setup
    own = upload(client, target, png)
    own_path, _, _ = repo.read_target_report_attachment(101, own)
    school = repo.create_school(202, SchoolCreate(admission_year=2026, school_name='독립학교'))
    other = repo.create_clinic_round(202, ClinicRoundCreate(
        school_id=school['id'], round_number=1, student_names=['독립 학생'],
        start_time=datetime.fromisoformat('2026-09-16T09:00:00+09:00'),
        end_time=datetime.fromisoformat('2026-09-16T10:00:00+09:00')))
    other_target = other['targets'][0]['id']
    repo.save_target_report_attachment(202, other_target, 'blank_test', 'other.png', 'image/png', png)
    other_file = next((repo.ATTACHMENT_ROOT / '202').rglob('*.png'))
    assert client.delete(f'/api/personal/aura/rounds/{session}').status_code == 204
    assert not own_path.exists()
    assert other_file.read_bytes() == png
