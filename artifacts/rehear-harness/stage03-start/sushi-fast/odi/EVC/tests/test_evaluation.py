import asyncio

from odi.EVC.evaluation import (
    EvaluationProviderError,
    compute_speech_metrics,
    evaluate_presentation_segment,
)
from odi.EVC.schema import (
    ContentScores,
    GPTDeliveryScores,
    SegmentContext,
    SegmentEvaluation,
    SlideInfo,
    SpeechTextResult,
    SpeechWord,
)


def provider_result() -> SegmentEvaluation:
    return SegmentEvaluation(
        move="Purpose",
        content=ContentScores(
            organization=0.4,
            supporting_material=0.2,
            central_message=0.5,
            cer_validity=0.1,
        ),
        delivery=GPTDeliveryScores(
            language_clarity=0.6,
            slide_speech_alignment=0.7,
        ),
        segment_note="핵심 목적을 소개함",
        short_reason="목적과 메시지가 명확함",
        missing_inputs=[],
        confidence=0.8,
    )


def test_speech_metrics_are_deterministic_and_bounded() -> None:
    result = SpeechTextResult(
        transcript="안녕 안녕 발표 입니다",
        words=[
            SpeechWord(word="안녕", start=0.0, end=0.4, confidence=0.9),
            SpeechWord(word="안녕", start=0.5, end=0.9, confidence=0.9),
            SpeechWord(word="발표", start=1.8, end=2.2, confidence=0.8),
            SpeechWord(word="입니다", start=2.3, end=2.8, confidence=0.8),
        ],
    )
    metrics = compute_speech_metrics(result)

    assert metrics.word_count == 4
    assert metrics.pause_count == 1
    assert metrics.repeated_word_count == 1
    assert -1.0 <= metrics.vocal_delivery_score <= 1.0


def test_evaluation_assembles_provider_audio_and_missing_inputs() -> None:
    class Provider:
        def evaluate(self, payload):
            assert "evc_state" not in payload
            assert "behavior" not in payload
            return provider_result()

    async def scenario() -> None:
        evaluation, metrics, warnings = await evaluate_presentation_segment(
            presentation_title="테스트",
            slides=[],
            segment_notes=[],
            stt_result=SpeechTextResult(
                transcript="발표 목적을 소개합니다",
                words=[SpeechWord(word="소개", start=0.0, end=0.5, confidence=0.4)],
            ),
            context=SegmentContext(
                current_slide_index=0,
                utterance_position="during_speech",
                language="ko-KR",
                gaze_delivery_score=None,
                client_time_s=1.0,
            ),
            provider=Provider(),
            retries=0,
        )
        assert evaluation.delivery.language_clarity == 0.6
        assert evaluation.delivery.vocal_delivery == metrics.vocal_delivery_score
        assert evaluation.delivery.gaze_delivery == 0.0
        assert evaluation.delivery.slide_speech_alignment == 0.0
        assert set(evaluation.missing_inputs) >= {
            "gaze_delivery_score",
            "slide_context",
            "low_stt_confidence",
        }
        assert warnings == ["low_stt_confidence"]

    asyncio.run(scenario())


def test_evaluation_provider_retries_without_creating_state_or_behavior() -> None:
    class FlakyProvider:
        def __init__(self) -> None:
            self.calls = 0

        def evaluate(self, payload):
            self.calls += 1
            if self.calls == 1:
                raise EvaluationProviderError("temporary")
            return provider_result()

    async def scenario() -> None:
        provider = FlakyProvider()
        evaluation, _, _ = await evaluate_presentation_segment(
            presentation_title="테스트",
            slides=[SlideInfo(index=0, title="목적", text="목적", summary="목적")],
            segment_notes=[],
            stt_result=SpeechTextResult(
                transcript="목적입니다",
                words=[SpeechWord(word="목적", start=0.0, end=0.5, confidence=0.9)],
            ),
            context=SegmentContext(
                current_slide_index=0,
                utterance_position="during_speech",
                language="ko-KR",
                gaze_delivery_score=0.2,
                client_time_s=1.0,
            ),
            provider=provider,
            retries=1,
        )
        assert provider.calls == 2
        assert evaluation.content.central_message == 0.5
        assert not hasattr(evaluation, "evc_state")
        assert not hasattr(evaluation, "behavior")

    asyncio.run(scenario())


def test_empty_transcript_skips_provider() -> None:
    class Provider:
        def evaluate(self, payload):
            raise AssertionError("provider must not be called for empty speech")

    async def scenario() -> None:
        evaluation, metrics, warnings = await evaluate_presentation_segment(
            presentation_title="테스트",
            slides=[],
            segment_notes=[],
            stt_result=SpeechTextResult(transcript="", words=[]),
            context=SegmentContext(client_time_s=0.0),
            provider=Provider(),
        )
        assert evaluation.confidence == 0.0
        assert evaluation.missing_inputs == ["latest_speech"]
        assert metrics.word_count == 0
        assert warnings == []

    asyncio.run(scenario())
