import pytest
from fastapi import HTTPException
from starlette.requests import Request

from personal_project import academic, native_kakao, report_pdf, router


def request():
    return Request({'type': 'http', 'method': 'POST', 'path': '/', 'headers': [(b'origin', b'https://aura.chobab.app')]})


@pytest.mark.parametrize('stage', list(academic.STAGE_LABELS) + ['grade1_semestar2_final'])
def test_pdf_stage_labels_cover_existing_and_legacy_typo(stage, tmp_path):
    report = {'progressStage': stage}
    html = report_pdf._html(report, [], tmp_path)
    normalized = stage.replace('semestar', 'semester')
    assert academic.STAGE_LABELS[normalized] in html
    assert stage not in html


@pytest.mark.parametrize('delivery', ['verified', 'failed', 'unknown', 'partial'])
def test_server_report_marks_complete_only_on_verified_delivery(monkeypatch, delivery, isolated_delivery_db):
    updates = []
    monkeypatch.setattr(router.repository, 'get_or_create_target_report', lambda *_: {'id': 7})
    monkeypatch.setattr(router.repository, 'update_target_report', lambda *a, **kw: updates.append((a, kw)))
    monkeypatch.setattr(native_kakao, 'create_clinic_job', lambda *_: {'jobId': 'synthetic', 'deliveryFormat': 'images'})
    monkeypatch.setattr(native_kakao, 'discard_clinic_job', lambda *_: None)
    monkeypatch.setattr(native_kakao, 'store_page', lambda *_: None)
    monkeypatch.setattr(router, '_target_report_pdf', lambda *_: b'pdf')
    monkeypatch.setattr(report_pdf, 'render_pages', lambda *a, **kw: [b'page'])
    def send(*_):
        if delivery != 'verified':
            raise native_kakao.NativeKakaoError(409, 'synthetic', delivery)
        return {'sent': True, 'deliveryStatus': 'verified'}
    monkeypatch.setattr(native_kakao, 'send_clinic_job', send)
    if delivery == 'verified':
        assert router.send_server_generated_clinic_report(50, request(), 3)['sent']
        assert updates == [((3, 7, None), {'submit': True})]
    else:
        with pytest.raises(HTTPException):
            router.send_server_generated_clinic_report(50, request(), 3)
        assert not updates


def test_real_pdf_contains_korean_stage():
    import fitz
    pdf = report_pdf.render_pdf({'progressStage': 'grade1_semestar2_final'}, [])
    doc = fitz.open(stream=pdf, filetype='pdf')
    text = ''.join(page.get_text() for page in doc)
    assert '1학년 2학기 기말고사' in text
    assert 'semestar' not in text


def test_synthetic_http_delivery_persists_only_verified_success(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from personal_project import db, kakao_bridge
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'synthetic.sqlite')
    db.init_db()
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[router.current_user_id] = lambda: 81234
    app.dependency_overrides[router.native_kakao_user_id] = lambda: 81234
    client = TestClient(app, headers={'origin': 'https://aura.chobab.app'})
    school = client.post('/api/personal/aura/schools', json={'admission_year': 2026, 'school_name': '합성학교'}).json()
    rounds = client.post('/api/personal/aura/rounds/series', json={
        'school_id': school['id'], 'progress_stage': 'grade1_semester2_final', 'round_number': 1,
        'student_names': ['가상학생'], 'start_time': '2026-11-08T10:00:00+09:00',
        'end_time': '2026-11-08T11:00:00+09:00', 'repeat_count': 1, 'interval_weeks': 1,
        'allow_overlap': True}).json()
    target = rounds[0]['targets'][0]['id']
    base = f'/api/personal/aura/targets/{target}'
    assert client.get(base + '/report').json()['status'] != 'submitted'
    outcome = {'fail_note': True}
    def invoke(command, **kwargs):
        if command == 'search':
            return {'opened': True, 'room': kwargs['room'], 'searchEvidence': 'unique_exact'}
        if outcome['fail_note'] and kwargs.get('text'):
            return {'sent': False}
        return {'sent': True}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    response = client.post(base + '/kakao-clinic/send-report')
    assert response.status_code == 409, response.text
    assert client.get(base + '/report').json()['status'] != 'submitted'
    outcome['fail_note'] = False
    response = client.post(base + '/kakao-clinic/send-report')
    assert response.status_code == 200, response.text
    assert client.get(base + '/report').json()['status'] == 'submitted'
