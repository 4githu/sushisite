from email.message import Message
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_project import ai_report, router
from personal_project.make_report_test import gemini_report_service as gemini


def test_provider_http_503_through_real_request_and_http_route(monkeypatch):
    # The only provider transport is a stub; no live request may leave the process.
    calls = []
    def fake_urlopen(request, timeout):
        calls.append(request.method)
        raise HTTPError('https://example.invalid/', 503, 'Unavailable', Message(), BytesIO(b'private fixture'))
    monkeypatch.setattr(gemini, 'urlopen', fake_urlopen)

    actual = gemini.GeminiReportService.__new__(gemini.GeminiReportService)
    actual.api_key = 'fixture'
    class SyntheticService:
        last_cache_mode = 'implicit'
        cache_notice = None
        @staticmethod
        def read_prompt(): return 'fixture'
        @staticmethod
        def prompt_hash(_): return 'hash'
        def __init__(self, **kwargs): pass
        def generate(self, **kwargs): return actual._request('POST', 'models/fixture:generateContent', {'fixture': True})
        def close(self): pass

    saved = []
    monkeypatch.setattr(ai_report.repository, 'get_or_create_target_report', lambda *a: None)
    monkeypatch.setattr(ai_report, 'migrate', lambda: None)
    monkeypatch.setattr(ai_report, 'build_report_input', lambda *a, **kw: {'target': {'userId': 10}})
    monkeypatch.setattr(ai_report, 'get_report_model', lambda _: SimpleNamespace(provider='gemini', explicit_cache=False))
    monkeypatch.setattr(ai_report, 'list_completed_runs', lambda _: [])
    monkeypatch.setattr(ai_report, 'find_completed_run', lambda *a: None)
    monkeypatch.setattr(ai_report, 'start_run', lambda *a, **kw: 123)
    monkeypatch.setattr(ai_report, 'finish_run', lambda *a, **kw: saved.append(kw))
    monkeypatch.setattr(ai_report, 'GeminiReportService', SyntheticService)
    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[router.current_user_id] = lambda: 10
    with TestClient(app) as client:
        response = client.post('/api/personal/aura/targets/20/ai-reports/generate', json={'model': 'fixture', 'score_mode': 'none'})
    assert calls == ['POST']
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'ai_report_provider_unavailable'
    assert saved == [{'error': 'provider_generate:GeminiReportError:api_http_503'}]
    assert 'private fixture' not in response.text
