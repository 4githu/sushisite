"""Exercise the real report/PDF path with synthetic data and a fake bridge."""
from personal_project import router, kakao_bridge, db
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_full_report_pdf_and_mocked_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'pdf-test.sqlite')
    db.init_db()
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[router.current_user_id] = lambda: 123
    app.dependency_overrides[router.native_kakao_user_id] = lambda: 123
    client = TestClient(app)
    school = client.post('/api/personal/aura/schools', json={'admission_year': 2026, 'school_name': '합성점검학교'}).json()
    rounds = client.post('/api/personal/aura/rounds/series', json={'school_id': school['id'], 'progress_stage': 'grade1_semester2_final', 'round_number': 1, 'student_names': ['합성점검학생'], 'start_time': '2026-11-08T10:00:00+09:00', 'end_time': '2026-11-08T11:00:00+09:00', 'repeat_count': 1, 'interval_weeks': 1, 'allow_overlap': True}).json()
    target = rounds[0]['targets'][0]['id']
    from personal_project.schemas import TargetReportUpdate
    report = router.repository.get_or_create_target_report(123, target)
    router.repository.update_target_report(123, report['id'], TargetReportUpdate(generated_report_json={'learningContent': {'paragraphs': ['합성 리포트 경로 점검']}}))
    def invoke(command, **kwargs):
        room = kwargs.get('room', '')
        if command == 'search':
            return {'found': False, 'room': room, 'searchEvidence': 'confirmed_absent'} if room != '본계정' else {'opened': True, 'room': room, 'searchEvidence': 'unique_exact'}
        return {'sent': True}
    monkeypatch.setattr(kakao_bridge, 'invoke', invoke)
    response = client.post(f'/api/personal/aura/targets/{target}/kakao-clinic/send-report', headers={'origin': 'https://aura.chobab.app'})
    assert response.status_code == 200, response.json()
    assert response.json()['deliveryStatus'] == 'verified'


def test_background_generation_preserves_concurrent_manual_edit(tmp_path, monkeypatch):
    from personal_project import clinic_scheduled_delivery as q
    from personal_project.schemas import TargetReportUpdate
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'race.sqlite')
    db.init_db()
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[router.current_user_id] = lambda: 123
    client = TestClient(app)
    school = client.post('/api/personal/aura/schools', json={'admission_year': 2026, 'school_name': '합성학교'}).json()
    rounds = client.post('/api/personal/aura/rounds/series', json={'school_id': school['id'], 'progress_stage': 'grade1_semester2_final', 'round_number': 1, 'student_names': ['합성학생'], 'start_time': '2026-11-08T10:00:00+09:00', 'end_time': '2026-11-08T11:00:00+09:00', 'repeat_count': 1, 'interval_weeks': 1, 'allow_overlap': True}).json()
    target = rounds[0]['targets'][0]['id']
    report = router.repository.get_or_create_target_report(123, target)
    manual = {'text': '수동 저장'}
    def provider(*args, **kwargs):
        router.repository.update_target_report(123, report['id'], TargetReportUpdate(generated_report_json=manual))
        return {'results': [{'output': {'text': '자동 생성'}, 'model': 'synthetic'}]}
    monkeypatch.setattr(q.ai_report, 'generate', provider)
    q._generate(123, target)
    assert router.repository.get_or_create_target_report(123, target)['generatedReportJson'] == manual
