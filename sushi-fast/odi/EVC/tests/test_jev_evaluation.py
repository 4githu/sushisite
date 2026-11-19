import json

import httpx
import pytest

from odi.EVC.evaluation import EvaluationProviderError, default_segment_provider
from odi.EVC.jev_evaluation import JevSegmentEvaluationProvider, RUBRICS
from odi.EVC.report_v2.report_generation import OpenAIReportInsightProvider


def response_body():
    return {"answers": {
        **{key: {"type": "score", "score": 1.5, "confidence": .8} for key in RUBRICS},
        "move": {"type": "choice", "choice": "Results", "confidence": .9}}}


def test_jev_request_mapping_and_report_separation(monkeypatch):
    def handle(request):
        body = json.loads(request.content)
        assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
        assert body["state"]["latest_speech"] == "test evidence"
        assert len(body["questions"]) == 7
        return httpx.Response(200, json=response_body())
    provider = JevSegmentEvaluationProvider("synthetic", transport=httpx.MockTransport(handle))
    result = provider.evaluate({"latest_speech": "test evidence"})
    assert result.content.organization == .5
    assert result.delivery.slide_speech_alignment == 0
    assert result.missing_inputs == ["slide_context"]
    assert result.move == "Results"
    assert result.confidence == .8
    monkeypatch.setenv("EVC_EVALUATION_PROVIDER", "jev")
    assert isinstance(default_segment_provider(), JevSegmentEvaluationProvider)
    assert OpenAIReportInsightProvider.__module__.endswith("report_v2.report_generation")


@pytest.mark.parametrize("value", [True, "1", -1, 3, float("inf")])
def test_rejects_invalid_scores(value):
    body = response_body()
    body["answers"]["organization"]["score"] = value
    # JSON itself cannot encode infinity: provide parsed content through a response stub.
    class Response:
        def raise_for_status(self): pass
        def json(self): return body
    from unittest.mock import patch
    with patch("httpx.Client.post", return_value=Response()):
        with pytest.raises(EvaluationProviderError):
            JevSegmentEvaluationProvider("synthetic").evaluate({})


def test_no_silent_gpt_fallback(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(EvaluationProviderError, match="not configured"):
        JevSegmentEvaluationProvider().evaluate({})
    monkeypatch.setenv("EVC_EVALUATION_PROVIDER", "typo")
    with pytest.raises(EvaluationProviderError):
        default_segment_provider()


@pytest.mark.parametrize("selection", [None, "gpt", "openai", " GPT "])
def test_gpt_default_and_explicit_selection(monkeypatch, selection):
    from odi.EVC.evaluation import OpenAISegmentEvaluationProvider
    if selection is None:
        monkeypatch.delenv("EVC_EVALUATION_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("EVC_EVALUATION_PROVIDER", selection)
    assert isinstance(default_segment_provider(), OpenAISegmentEvaluationProvider)
