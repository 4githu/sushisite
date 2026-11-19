import pytest

from personal_project.ai_report import _safe_generation_error
from personal_project.make_report_test.gemini_report_service import (
    GeminiReportError,
    GeminiReportService,
)


def test_empty_gemini_response_has_safe_diagnostic_code():
    try:
        GeminiReportService._response_json(
            {"candidates": []}
        )
    except GeminiReportError as exc:
        assert exc.diagnostic_code == "empty_response"
    else:
        raise AssertionError("expected GeminiReportError")


@pytest.mark.parametrize("response", [
    {
        "promptFeedback": {
            "blockReason": "PROHIBITED_CONTENT",
            "blockReasonMessage": "private fixture",
        },
        "promptTokenCount": 39688,
        "candidates": [],
    },
    {"candidates": [{"finishReason": "PROHIBITED_CONTENT", "content": {"parts": [{"text": "private fixture"}]}}]},
])
def test_provider_block_is_classified_without_echoing_feedback(response):
    with pytest.raises(GeminiReportError) as raised:
        GeminiReportService._response_json(response)
    assert raised.value.diagnostic_code == "provider_blocked_prohibited_content"
    assert "private fixture" not in str(raised.value)
    assert "39688" not in str(raised.value)


def test_generation_error_diagnostic_does_not_include_raw_provider_detail():
    exc = GeminiReportError(
        "raw provider body with student text and secret-like content",
        diagnostic_code="empty_response",
    )
    safe = _safe_generation_error("provider_generate", exc)
    assert safe == "provider_generate:GeminiReportError:empty_response"
    assert "raw provider body" not in safe
    assert "student text" not in safe
    assert "secret-like" not in safe


@pytest.mark.parametrize("diagnostic,expected_status", [
    ("empty_response", 502), ("provider_blocked_prohibited_content", 422),
])
def test_generate_persists_and_returns_only_safe_failure_metadata(monkeypatch, diagnostic, expected_status):
    from types import SimpleNamespace

    import pytest
    from fastapi import HTTPException
    from personal_project import ai_report

    persisted = []

    class FakeService:
        last_cache_mode = "implicit"
        cache_notice = None

        @staticmethod
        def read_prompt():
            return "prompt"

        @staticmethod
        def prompt_hash(_prompt):
            return "hash"

        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            raise GeminiReportError(
                "raw provider response containing student text",
                diagnostic_code=diagnostic,
            )

        def close(self):
            pass

    monkeypatch.setattr(ai_report.repository, "get_or_create_target_report", lambda *args: None)
    monkeypatch.setattr(ai_report, "migrate", lambda: None)
    monkeypatch.setattr(
        ai_report,
        "build_report_input",
        lambda *args, **kwargs: {"target": {"userId": 10}, "options": {}},
    )
    monkeypatch.setattr(
        ai_report,
        "get_report_model",
        lambda _model: SimpleNamespace(provider="gemini", explicit_cache=False),
    )
    monkeypatch.setattr(ai_report, "list_completed_runs", lambda _target: [])
    monkeypatch.setattr(ai_report.GeminiReportService, "read_prompt", lambda: "prompt")
    monkeypatch.setattr(ai_report.GeminiReportService, "prompt_hash", lambda _prompt: "hash")
    monkeypatch.setattr(ai_report, "find_completed_run", lambda *args: None)
    monkeypatch.setattr(ai_report, "start_run", lambda *args, **kwargs: 123)
    monkeypatch.setattr(ai_report, "finish_run", lambda *args, **kwargs: persisted.append(kwargs))
    monkeypatch.setattr(ai_report, "GeminiReportService", FakeService)

    with pytest.raises(HTTPException) as raised:
        ai_report.generate(10, 20, model="gemini-test", score_mode="none")

    expected = "provider_generate:GeminiReportError:" + diagnostic
    assert raised.value.status_code == expected_status
    assert raised.value.detail["retryable"] is (expected_status != 422)
    if expected_status == 422:
        assert raised.value.detail["code"] == "ai_report_provider_blocked"
        assert "자료의 생성을 제한했습니다" in raised.value.detail["message"]
        assert "같은 자료로 재시도해도 해결되지 않을 수 있습니다" in raised.value.detail["message"]
    else:
        assert raised.value.detail["code"] == "ai_report_generation_failed"
    assert raised.value.detail["errors"][0]["message"] == expected
    assert persisted == [{"error": expected}]
    assert "student text" not in str(raised.value.detail)
