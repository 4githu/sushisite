import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from odi.EVC.evaluation import EvaluationProviderError
from odi.EVC.observability import build_update_log_event, prune_debug_logs, record_update
from odi.EVC.router import _http_error
from odi.EVC.schema import (
    AudienceDecision,
    AudienceState,
    ContentScores,
    DeliveryScores,
    EVCUpdateResponseV2,
    MtDtEvaluation,
    SpeechMetrics,
    StateDeltaBreakdown,
    StateSensitivity,
)
from odi.EVC.session_store import SessionNotFoundError, SessionStore
from odi.EVC.schema import SmartStartOptions
from odi.EVC.speech2text import STTProviderError


def response_with_sensitive_source_text() -> EVCUpdateResponseV2:
    zero = AudienceState(E=0.0, V=0.0, C=0.0)
    decisions = [
        AudienceDecision(
            agent_id=f"audience_{index:02d}",
            previous_state=zero,
            sensitivity=StateSensitivity(E=1.0, V=1.0, C=1.0),
            state=zero,
            dominant_axis=None,
            direction=None,
            core_behavior=None,
            action_overlay=None,
            no_op_reason="empty_transcript",
        )
        for index in range(1, 7)
    ]
    return EVCUpdateResponseV2(
        request_id=uuid4(),
        session_id=uuid4(),
        step=0,
        accepted_client_time_s=1.0,
        latest_speech="PRIVATE PRESENTATION TRANSCRIPT",
        current_slide_index=0,
        speech_metrics=SpeechMetrics(
            duration_s=0.0,
            word_count=0,
            speech_rate_wps=0.0,
            pause_count=0,
            pause_total_s=0.0,
            filler_count=0,
            repeated_word_count=0,
            avg_confidence=0.0,
            vocal_delivery_score=0.0,
        ),
        evaluation=MtDtEvaluation(
            move="Unknown",
            content=ContentScores(
                organization=0.0,
                supporting_material=0.0,
                central_message=0.0,
                cer_validity=0.0,
            ),
            delivery=DeliveryScores(
                language_clarity=0.0,
                vocal_delivery=0.0,
                gaze_delivery=0.0,
                slide_speech_alignment=0.0,
            ),
            segment_note="PRIVATE NOTE",
            short_reason="PRIVATE REASON",
            missing_inputs=["latest_speech"],
            confidence=0.0,
        ),
        delta=StateDeltaBreakdown(content=zero, delivery=zero, common=zero),
        evc_state=zero,
        behavior=None,
        audiences=decisions,
        commands=[],
        no_op_reason="empty_transcript",
    )


def test_observability_event_excludes_transcript_evaluation_and_tokens() -> None:
    event = build_update_log_event(
        response_with_sensitive_source_text(),
        latency_ms=12.5,
        stt_provider="FakeSTT",
        evaluation_provider="skipped",
    )
    serialized = json.dumps(event)
    assert "PRIVATE" not in serialized
    assert "latest_speech" not in serialized
    assert "segment_note" not in serialized
    assert "short_reason" not in serialized
    assert "token" not in serialized.lower()


def test_debug_metadata_write_and_retention(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("odi.EVC.observability.EVC_DEBUG_LOG", True)
    monkeypatch.setattr("odi.EVC.observability.EVC_DEBUG_LOG_DIR", tmp_path)
    response = response_with_sensitive_source_text()
    record_update(
        response,
        latency_ms=1.0,
        stt_provider="FakeSTT",
        evaluation_provider="skipped",
    )
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    assert "PRIVATE" not in files[0].read_text(encoding="utf-8")

    os.utime(files[0], (0, 0))
    assert prune_debug_logs(tmp_path, retention_days=1, now=2 * 86400) == 1
    assert not files[0].exists()


def test_provider_http_errors_do_not_expose_raw_exception_details() -> None:
    stt = _http_error(STTProviderError("secret-key-in-provider-error"))
    evaluation = _http_error(EvaluationProviderError("private prompt content"))
    assert stt.detail["message"] == "STT provider failed"
    assert evaluation.detail["message"] == "Evaluation provider failed"


def test_expired_session_removes_owned_slide_file(tmp_path: Path) -> None:
    async def scenario() -> None:
        now = [1.0]
        slide = tmp_path / "slide.pdf"
        slide.write_bytes(b"pdf")
        store = SessionStore(ttl_s=10, monotonic_clock=lambda: now[0])
        record, token = await store.create_session(
            SmartStartOptions(presentation_title="test", seed=1),
            slide_file_path=str(slide),
        )
        now[0] = 12.0
        try:
            await store.get_authorized_session(record.session_id, token)
        except SessionNotFoundError:
            pass
        else:
            raise AssertionError("expired session must not be returned")
        assert not slide.exists()

    asyncio.run(scenario())
