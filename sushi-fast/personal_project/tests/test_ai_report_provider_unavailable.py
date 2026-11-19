from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from personal_project import ai_report
from personal_project.make_report_test.gemini_report_service import GeminiReportError


def test_provider_503_has_safe_temporary_unavailable_guidance(monkeypatch):
    persisted = []

    class FakeService:
        last_cache_mode = "implicit"
        cache_notice = None

        def __init__(self, **kwargs):
            pass

        @staticmethod
        def read_prompt():
            return "fixture"

        @staticmethod
        def prompt_hash(_prompt):
            return "hash"

        def generate(self, **kwargs):
            raise GeminiReportError("sensitive fixture", diagnostic_code="api_http_503")

        def close(self):
            pass

    monkeypatch.setattr(ai_report.repository, "get_or_create_target_report", lambda *args: None)
    monkeypatch.setattr(ai_report, "migrate", lambda: None)
    monkeypatch.setattr(ai_report, "build_report_input", lambda *a, **kw: {"target": {"userId": 10}})
    monkeypatch.setattr(ai_report, "get_report_model", lambda _: SimpleNamespace(provider="gemini", explicit_cache=False))
    monkeypatch.setattr(ai_report, "list_completed_runs", lambda _: [])
    monkeypatch.setattr(ai_report, "find_completed_run", lambda *args: None)
    monkeypatch.setattr(ai_report, "start_run", lambda *a, **kw: 123)
    monkeypatch.setattr(ai_report, "finish_run", lambda *a, **kw: persisted.append(kw))
    monkeypatch.setattr(ai_report, "GeminiReportService", FakeService)

    with pytest.raises(HTTPException) as raised:
        ai_report.generate(10, 20, model="gemini-test", score_mode="none")
    assert raised.value.status_code == 502
    assert raised.value.detail["code"] == "ai_report_provider_unavailable"
    assert raised.value.detail["retryable"] is True
    assert "잠시 후 다시 시도" in raised.value.detail["message"]
    assert "sensitive fixture" not in str(raised.value.detail)
    assert persisted == [{"error": "provider_generate:GeminiReportError:api_http_503"}]

    # Exercise the same HTTP route with an isolated app and a synthetic provider.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from personal_project import router

    app = FastAPI()
    app.include_router(router.router)
    app.dependency_overrides[router.current_user_id] = lambda: 10
    with TestClient(app) as client:
        response = client.post(
            "/api/personal/aura/targets/20/ai-reports/generate",
            json={"model": "gemini-test", "score_mode": "none"},
        )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ai_report_provider_unavailable"
    assert "잠시 후 다시 시도" in response.json()["detail"]["message"]
    assert "sensitive fixture" not in response.text
