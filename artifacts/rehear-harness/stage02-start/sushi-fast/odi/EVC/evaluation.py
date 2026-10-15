from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Protocol

from .config import EVC_LLM_TIMEOUT_S, EVC_PROVIDER_RETRIES, OPENAI_EVC_MODEL
from .schema import (
    ContentScores,
    DeliveryScores,
    GPTDeliveryScores,
    MtDtEvaluation,
    SegmentContext,
    SegmentEvaluation,
    SlideInfo,
    SpeechMetrics,
    SpeechTextResult,
    clamp,
)


SYSTEM_PROMPT = """
You are the segment evaluator for the Re:hear XR presentation training system.
Evaluate only the current presentation segment. Do not generate audience E/V/C
state, behavior IDs, animation names, or Unity commands.

Return the response_format fields only. Content scores are organization,
supporting_material, central_message, and cer_validity. Delivery scores produced
by you are language_clarity and slide_speech_alignment. Every score is a finite
float from -1.0 to +1.0. Do not guess unavailable information; use 0.0 and add
its name to missing_inputs. Keep segment_note and short_reason concise. Lower
confidence for incomplete or very short speech.
""".strip()


class EvaluationProviderError(RuntimeError):
    pass


class SegmentEvaluationProvider(Protocol):
    def evaluate(self, payload: dict[str, Any]) -> SegmentEvaluation: ...


class OpenAISegmentEvaluationProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = OPENAI_EVC_MODEL,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

    def evaluate(self, payload: dict[str, Any]) -> SegmentEvaluation:
        if not self.api_key:
            raise EvaluationProviderError("OPENAI_API_KEY is not configured")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EvaluationProviderError("openai package is not installed") from exc

        try:
            client = OpenAI(api_key=self.api_key)
            completion = client.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    },
                ],
                response_format=SegmentEvaluation,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise EvaluationProviderError(
                    "OpenAI response could not be parsed as SegmentEvaluation"
                )
            return parsed
        except EvaluationProviderError:
            raise
        except Exception as exc:
            raise EvaluationProviderError(f"OpenAI segment evaluation failed: {exc}") from exc


def compute_speech_metrics(result: SpeechTextResult) -> SpeechMetrics:
    words = result.words
    if not words:
        return SpeechMetrics(
            duration_s=0.0,
            word_count=0,
            speech_rate_wps=0.0,
            pause_count=0,
            pause_total_s=0.0,
            filler_count=0,
            repeated_word_count=0,
            avg_confidence=0.0,
            vocal_delivery_score=0.0,
        )

    start_time = min(word.start for word in words)
    end_time = max(word.end for word in words)
    duration_s = max(0.1, end_time - start_time)
    word_count = len(words)
    speech_rate_wps = word_count / duration_s
    pauses = [
        current.start - previous.end
        for previous, current in zip(words, words[1:])
        if current.start - previous.end >= 0.7
    ]
    filler_words = {"어", "음", "그", "저", "아", "뭐", "그러니까", "약간"}
    filler_count = sum(1 for word in words if word.word.strip().lower() in filler_words)
    repeated_word_count = sum(
        1 for previous, current in zip(words, words[1:]) if previous.word == current.word
    )
    avg_confidence = sum(word.confidence for word in words) / word_count
    vocal_score = compute_vocal_delivery_score(
        speech_rate_wps=speech_rate_wps,
        pause_total_s=sum(pauses),
        filler_count=filler_count,
        repeated_word_count=repeated_word_count,
        avg_confidence=avg_confidence,
        duration_s=duration_s,
        word_count=word_count,
    )
    return SpeechMetrics(
        duration_s=duration_s,
        word_count=word_count,
        speech_rate_wps=speech_rate_wps,
        pause_count=len(pauses),
        pause_total_s=sum(pauses),
        filler_count=filler_count,
        repeated_word_count=repeated_word_count,
        avg_confidence=avg_confidence,
        vocal_delivery_score=vocal_score,
    )


def compute_vocal_delivery_score(
    *,
    speech_rate_wps: float,
    pause_total_s: float,
    filler_count: int,
    repeated_word_count: int,
    avg_confidence: float,
    duration_s: float,
    word_count: int,
) -> float:
    score = 0.0
    if 1.6 <= speech_rate_wps <= 3.5:
        score += 0.25
    elif speech_rate_wps < 0.8 or speech_rate_wps > 4.5:
        score -= 0.35
    else:
        score -= 0.10

    pause_ratio = pause_total_s / max(0.1, duration_s)
    score += -0.30 if pause_ratio > 0.35 else -0.15 if pause_ratio > 0.20 else 0.10
    filler_ratio = filler_count / max(1, word_count)
    score += -0.30 if filler_ratio > 0.15 else -0.15 if filler_ratio > 0.07 else 0.10
    repeated_ratio = repeated_word_count / max(1, word_count)
    if repeated_ratio > 0.10:
        score -= 0.20
    elif repeated_ratio == 0:
        score += 0.05
    if avg_confidence >= 0.90:
        score += 0.15
    elif avg_confidence < 0.70:
        score -= 0.20
    return clamp(score)


def build_evaluation_payload(
    *,
    presentation_title: str,
    slides: list[SlideInfo],
    segment_notes: list[str],
    latest_speech: str,
    speech_metrics: SpeechMetrics,
    context: SegmentContext,
) -> dict[str, Any]:
    current_slide = slides[context.current_slide_index].model_dump() if slides else None
    return {
        "presentation_title": presentation_title,
        "slides_outline": [
            {"index": slide.index, "title": slide.title, "summary": slide.summary}
            for slide in slides
        ],
        "current_slide": current_slide,
        "recent_segment_notes": segment_notes[-8:],
        "latest_speech": latest_speech,
        "speech_metrics": speech_metrics.model_dump(),
        "utterance_position": context.utterance_position,
    }


async def request_segment_evaluation(
    payload: dict[str, Any],
    *,
    provider: SegmentEvaluationProvider | None = None,
    timeout_s: int = EVC_LLM_TIMEOUT_S,
    retries: int = EVC_PROVIDER_RETRIES,
) -> SegmentEvaluation:
    selected = provider or OpenAISegmentEvaluationProvider()
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(selected.evaluate, payload),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as exc:
            last_error = EvaluationProviderError(
                f"segment evaluation timed out after {timeout_s} seconds"
            )
            last_error.__cause__ = exc
        except EvaluationProviderError as exc:
            last_error = exc
        except Exception as exc:
            last_error = EvaluationProviderError(f"segment evaluator failed: {exc}")
        if attempt < retries:
            await asyncio.sleep(0)
    assert last_error is not None
    raise last_error


def assemble_mt_dt(
    gpt_evaluation: SegmentEvaluation,
    speech_metrics: SpeechMetrics,
    context: SegmentContext,
    *,
    has_slides: bool,
) -> tuple[MtDtEvaluation, list[str]]:
    missing = list(dict.fromkeys(gpt_evaluation.missing_inputs))
    warnings: list[str] = []
    gaze_score = context.gaze_delivery_score
    if gaze_score is None:
        gaze_score = 0.0
        missing.append("gaze_delivery_score")
    if not has_slides:
        missing.append("slide_context")
    if speech_metrics.avg_confidence < 0.50:
        missing.append("low_stt_confidence")
        warnings.append("low_stt_confidence")

    evaluation = MtDtEvaluation(
        move=gpt_evaluation.move,
        content=gpt_evaluation.content,
        delivery=DeliveryScores(
            language_clarity=gpt_evaluation.delivery.language_clarity,
            vocal_delivery=speech_metrics.vocal_delivery_score,
            gaze_delivery=gaze_score,
            slide_speech_alignment=(
                gpt_evaluation.delivery.slide_speech_alignment if has_slides else 0.0
            ),
        ),
        segment_note=gpt_evaluation.segment_note,
        short_reason=gpt_evaluation.short_reason,
        missing_inputs=list(dict.fromkeys(missing)),
        confidence=gpt_evaluation.confidence,
    )
    return evaluation, warnings


async def evaluate_presentation_segment(
    *,
    presentation_title: str,
    slides: list[SlideInfo],
    segment_notes: list[str],
    stt_result: SpeechTextResult,
    context: SegmentContext,
    provider: SegmentEvaluationProvider | None = None,
    timeout_s: int = EVC_LLM_TIMEOUT_S,
    retries: int = EVC_PROVIDER_RETRIES,
) -> tuple[MtDtEvaluation, SpeechMetrics, list[str]]:
    metrics = compute_speech_metrics(stt_result)
    if not stt_result.transcript.strip():
        return empty_evaluation(), metrics, []
    payload = build_evaluation_payload(
        presentation_title=presentation_title,
        slides=slides,
        segment_notes=segment_notes,
        latest_speech=stt_result.transcript,
        speech_metrics=metrics,
        context=context,
    )
    provider_evaluation = await request_segment_evaluation(
        payload,
        provider=provider,
        timeout_s=timeout_s,
        retries=retries,
    )
    evaluation, warnings = assemble_mt_dt(
        provider_evaluation,
        metrics,
        context,
        has_slides=bool(slides),
    )
    return evaluation, metrics, warnings


def empty_evaluation() -> MtDtEvaluation:
    return MtDtEvaluation(
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
        segment_note="",
        short_reason="No speech transcript was available for evaluation.",
        missing_inputs=["latest_speech"],
        confidence=0.0,
    )
