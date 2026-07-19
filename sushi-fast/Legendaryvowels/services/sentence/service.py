import os
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4

from ...schemas import (
    AnalysisStatus,
    AlignmentEvidence,
    AudioMetrics,
    EvaluationScore,
    Feedback,
    PracticeItem,
    ProductMode,
    SpeechTextResult,
    SttMetadata,
    TranscriptInfo,
    VoiceEvaluationResponse,
    WordResult,
    WordTiming,
)
from ..audio import analyze_audio
from ..rules import (
    AUDIO_RULES,
    DELIVERY_SCORE_RULES,
    FILLER_WORDS,
    MISMATCH_RULES,
    PRACTICE_RESOURCES,
    VERIFICATION_RULES,
)
from ..stt.deepgram import speech_to_text_detail
from ..stt.google import create_google_verification_stt
from .alignment import align_text, normalize_text
from .scoring import calculate_delivery_score_components


CONFIDENCE_NOTE = (
    "STT 전사에서 관측된 차이이며 실제 발음 또는 조음 상태를 "
    "단정하지 않습니다."
)
PRIMARY_STT_MODEL = os.getenv("DEEPGRAM_PRIMARY_MODEL", "nova-3")
VERIFICATION_STT_MODEL = os.getenv("DEEPGRAM_VERIFICATION_MODEL")
VERIFICATION_STT_PROVIDER = os.getenv("STT_VERIFICATION_PROVIDER", "google").lower()


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _verification_enabled() -> bool:
    return (
        _env_flag("STT_VERIFICATION_ENABLED")
        or _env_flag("GOOGLE_STT_VERIFICATION_ENABLED")
        or VERIFICATION_STT_MODEL is not None
    )


def _verification_thresholds() -> tuple[float, float]:
    return (
        _env_float(
            "STT_VERIFICATION_MIN_AVERAGE_CONFIDENCE",
            VERIFICATION_RULES.minimum_average_confidence,
        ),
        _env_float(
            "STT_VERIFICATION_MIN_TARGET_SIMILARITY",
            VERIFICATION_RULES.minimum_target_similarity,
        ),
    )


def _run_verification_stt(audio_path: str) -> tuple[SpeechTextResult, str, str | None]:
    if VERIFICATION_STT_PROVIDER == "google":
        verifier = create_google_verification_stt()
        return verifier.transcribe(audio_path), "google", verifier.model or "default"
    if VERIFICATION_STT_PROVIDER == "deepgram":
        model = VERIFICATION_STT_MODEL or PRIMARY_STT_MODEL
        return speech_to_text_detail(audio_path, model=model), "deepgram", model
    raise RuntimeError(
        f"지원하지 않는 STT 검증 provider입니다: {VERIFICATION_STT_PROVIDER}"
    )


def _count_fillers(transcript: str) -> int:
    return sum(
        token in FILLER_WORDS
        for token in transcript.replace(",", " ").split()
    )


def _to_word_timings(stt_result: SpeechTextResult) -> list[WordTiming]:
    return [
        WordTiming(
            transcript_index=index,
            text=word.word,
            start_sec=word.start,
            end_sec=word.end,
            stt_confidence=word.confidence,
        )
        for index, word in enumerate(stt_result.words)
    ]


def _build_feedback(word_results: list[WordResult]) -> Feedback:
    if not word_results:
        return Feedback(
            status="AVAILABLE",
            summary="목표 문장과 STT 전사문에서 다른 부분이 관측되지 않았습니다.",
            next_action="같은 문장을 한 번 더 자연스럽게 말해 보세요.",
        )

    practice_items: list[PracticeItem] = []
    descriptions: list[str] = []

    for result in word_results[:3]:
        if result.expected:
            practice_items.append(
                PracticeItem(
                    expected=result.expected,
                    recognized=result.recognized,
                    practice_resource_id=(
                        result.practice.practice_resource_id
                        if result.practice
                        else PRACTICE_RESOURCES.get(result.expected)
                    ),
                    articulation_tip_id=(
                        result.practice.articulation_tip_id
                        if result.practice
                        else None
                    ),
                    tip=(result.practice.tip if result.practice else None),
                )
            )

        if result.observation:
            descriptions.append(result.observation.message)
        elif result.status.value == "SUBSTITUTION":
            descriptions.append(
                f"목표 단어 '{result.expected}'가 STT에서 "
                f"'{result.recognized}'로 다르게 인식되었습니다."
            )

    return Feedback(
        status="AVAILABLE",
        summary=" ".join(descriptions),
        practice_items=practice_items,
        next_action=(
            "표시된 STT 관측 차이와 조음 Tip을 확인한 뒤 같은 문장을 "
            "다시 녹음해 보세요."
        ),
    )


def _transcript_info(
    *,
    transcript: str,
    target_text: str | None,
    text_accuracy_applicable: bool,
    generated_from_audio: bool = False,
) -> TranscriptInfo:
    return TranscriptInfo(
        raw_transcript=transcript,
        display_transcript=transcript,
        target_text=target_text,
        generated_from_audio=generated_from_audio,
        text_accuracy_applicable=text_accuracy_applicable,
    )


def _alignment_evidence() -> AlignmentEvidence:
    return AlignmentEvidence(
        evidence_type="STT_TEXT_ALIGNMENT",
        description=(
            "Deepgram 단어 전사 결과를 목표 문장과 단어/음절 단위로 정렬한 "
            "텍스트 기반 근거입니다."
        ),
        limitation=(
            "STT는 언어 모델 보정을 포함할 수 있으므로 실제 음소 관측이나 "
            "조음 상태를 단정하지 않습니다."
        ),
    )


def _undetermined_response(
    *,
    request_id: str,
    session_id: str,
    attempt_id: str,
    mode: ProductMode,
    target_text: str | None,
    retry_reason: str,
    transcript: str = "",
    metrics: AudioMetrics | None = None,
    verification_used: bool = False,
    verification_agreement: bool | None = None,
    verification_provider: str | None = None,
    verification_model: str | None = None,
) -> VoiceEvaluationResponse:
    return VoiceEvaluationResponse(
        request_id=request_id,
        session_id=session_id,
        attempt_id=attempt_id,
        mode=mode,
        analysis_status=AnalysisStatus.UNDETERMINED,
        requires_retry=True,
        retry_reason=retry_reason,
        needs_repractice=False,
        target_text=target_text,
        transcript=transcript,
        transcript_info=_transcript_info(
            transcript=transcript,
            target_text=target_text,
            text_accuracy_applicable=bool(target_text),
        ),
        confidence_note=CONFIDENCE_NOTE,
        stt=SttMetadata(
            provider="deepgram",
            model=PRIMARY_STT_MODEL,
            verification_used=verification_used,
            verification_agreement=verification_agreement,
            verification_provider=verification_provider,
            verification_model=verification_model,
        ),
        alignment_evidence=_alignment_evidence(),
        score=EvaluationScore(
            score_basis="INSUFFICIENT_EVIDENCE",
            matched_syllable_count=0,
            total_target_syllable_count=len(normalize_text(target_text or "")),
        ),
        metrics=metrics,
        feedback=Feedback(
            status="UNAVAILABLE",
            summary="분석 근거가 충분하지 않아 결과를 확정하지 않았습니다.",
            next_action="음성을 다시 녹음해 주세요.",
        ),
    )


def analyze_voice(
    *,
    audio_path: str,
    mode: ProductMode | str,
    session_id: str,
    attempt_id: str,
    target_text: str | None = None,
    request_id: str | None = None,
) -> VoiceEvaluationResponse:
    request_id = request_id or str(uuid4())
    mode = ProductMode(mode)
    target_text = target_text.strip() if target_text else None

    if not Path(audio_path).exists():
        raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {audio_path}")
    if mode == ProductMode.EDUCATION and not target_text:
        raise ValueError("education 모드에서는 target_text가 필요합니다.")
    if not session_id.strip() or not attempt_id.strip():
        raise ValueError("session_id와 attempt_id는 비어 있을 수 없습니다.")

    try:
        initial_metrics = analyze_audio(audio_path)
    except (ValueError, OSError):
        return _undetermined_response(
            request_id=request_id,
            session_id=session_id,
            attempt_id=attempt_id,
            mode=mode,
            target_text=target_text,
            retry_reason="INVALID_AUDIO",
        )

    if initial_metrics.duration_sec < AUDIO_RULES.minimum_duration_sec:
        return _undetermined_response(
            request_id=request_id,
            session_id=session_id,
            attempt_id=attempt_id,
            mode=mode,
            target_text=target_text,
            retry_reason="AUDIO_TOO_SHORT",
            metrics=initial_metrics,
        )
    if initial_metrics.peak_rms < AUDIO_RULES.minimum_peak_rms:
        return _undetermined_response(
            request_id=request_id,
            session_id=session_id,
            attempt_id=attempt_id,
            mode=mode,
            target_text=target_text,
            retry_reason="AUDIO_TOO_QUIET",
            metrics=initial_metrics,
        )

    try:
        stt_result = speech_to_text_detail(
            audio_path,
            model=PRIMARY_STT_MODEL,
        )
    except RuntimeError:
        return _undetermined_response(
            request_id=request_id,
            session_id=session_id,
            attempt_id=attempt_id,
            mode=mode,
            target_text=target_text,
            retry_reason="STT_SERVICE_ERROR",
            metrics=initial_metrics,
        )

    transcript = stt_result.transcript.strip()
    if not transcript:
        return _undetermined_response(
            request_id=request_id,
            session_id=session_id,
            attempt_id=attempt_id,
            mode=mode,
            target_text=target_text,
            retry_reason="EMPTY_TRANSCRIPT",
            metrics=initial_metrics,
        )

    average_confidence = (
        sum(word.confidence for word in stt_result.words) / len(stt_result.words)
        if stt_result.words
        else 0.0
    )
    target_similarity = (
        SequenceMatcher(
            None,
            normalize_text(target_text),
            normalize_text(transcript),
        ).ratio()
        if target_text
        else 1.0
    )
    verification_used = False
    verification_agreement: bool | None = None
    verification_provider: str | None = None
    verification_model: str | None = None
    minimum_average_confidence, minimum_target_similarity = _verification_thresholds()
    should_verify = (
        _verification_enabled()
        and (
            average_confidence
            < minimum_average_confidence
            or target_similarity
            < minimum_target_similarity
        )
    )
    if should_verify:
        verification_used = True
        try:
            (
                verification_result,
                verification_provider,
                verification_model,
            ) = _run_verification_stt(audio_path)
        except RuntimeError:
            return _undetermined_response(
                request_id=request_id,
                session_id=session_id,
                attempt_id=attempt_id,
                mode=mode,
                target_text=target_text,
                retry_reason="STT_VERIFICATION_ERROR",
                transcript=transcript,
                metrics=initial_metrics,
                verification_used=True,
                verification_provider=VERIFICATION_STT_PROVIDER,
            )

        verification_agreement = (
            normalize_text(transcript)
            == normalize_text(verification_result.transcript)
        )
        if not verification_agreement:
            return _undetermined_response(
                request_id=request_id,
                session_id=session_id,
                attempt_id=attempt_id,
                mode=mode,
                target_text=target_text,
                retry_reason="STT_VERIFICATION_DISAGREEMENT",
                transcript=transcript,
                metrics=initial_metrics,
                verification_used=True,
                verification_agreement=False,
                verification_provider=verification_provider,
                verification_model=verification_model,
            )

    normalized_transcript = normalize_text(transcript)
    metrics = analyze_audio(
        audio_path,
        spoken_character_count=len(normalized_transcript),
        filler_count=_count_fillers(transcript),
    )
    timing_score: float | None = None
    pause_score: float | None = None
    fluency_score: float | None = None
    delivery_score: float | None = None
    if mode == ProductMode.PRESENTATION:
        (
            timing_score,
            pause_score,
            fluency_score,
            delivery_score,
        ) = calculate_delivery_score_components(metrics, stt_result.words)
    word_results: list[WordResult] = []
    matched_count = 0
    total_count = 0
    text_score: float | None = None

    if target_text:
        alignment = align_text(target_text, transcript, stt_result.words)
        word_results = alignment.word_results
        if verification_used and verification_agreement:
            for word_result in word_results:
                word_result.evidence_source = "STT_CONSENSUS"
        matched_count = alignment.matched_syllable_count
        total_count = alignment.total_target_syllable_count
        text_score = round(matched_count / total_count * 100.0, 2) if total_count else 0.0

        if (
            text_score < MISMATCH_RULES.maximum_text_score
            and len(normalized_transcript)
            > max(
                MISMATCH_RULES.minimum_transcript_characters,
                total_count * MISMATCH_RULES.target_length_multiplier,
            )
        ):
            return _undetermined_response(
                request_id=request_id,
                session_id=session_id,
                attempt_id=attempt_id,
                mode=mode,
                target_text=target_text,
                retry_reason="TARGET_TRANSCRIPT_MISMATCH",
                transcript=transcript,
                metrics=metrics,
                verification_used=verification_used,
                verification_agreement=verification_agreement,
            )

    if mode == ProductMode.EDUCATION:
        overall_score = text_score
        score_basis = "STT_TEXT_ALIGNMENT"
    elif text_score is None:
        overall_score = delivery_score
        score_basis = "DELIVERY_METRICS"
    else:
        overall_score = round(
            text_score * DELIVERY_SCORE_RULES.presentation_text_weight
            + delivery_score
            * DELIVERY_SCORE_RULES.presentation_delivery_weight,
            2,
        )
        score_basis = "TEXT_ALIGNMENT_AND_DELIVERY"

    needs_repractice = bool(word_results)
    return VoiceEvaluationResponse(
        request_id=request_id,
        session_id=session_id,
        attempt_id=attempt_id,
        mode=mode,
        analysis_status=AnalysisStatus.COMPLETED,
        requires_retry=False,
        needs_repractice=needs_repractice,
        target_text=target_text,
        transcript=transcript,
        confidence_note=CONFIDENCE_NOTE,
        stt=SttMetadata(
            provider="deepgram",
            model=PRIMARY_STT_MODEL,
            verification_used=verification_used,
            verification_agreement=verification_agreement,
            verification_provider=verification_provider,
            verification_model=verification_model,
        ),
        score=EvaluationScore(
            overall_score=overall_score,
            text_match_score=text_score,
            timing_score=timing_score,
            pause_score=pause_score,
            fluency_score=fluency_score,
            delivery_score=delivery_score,
            score_basis=score_basis,
            matched_syllable_count=matched_count,
            total_target_syllable_count=total_count,
        ),
        words=_to_word_timings(stt_result),
        word_results=word_results,
        metrics=metrics,
        transcript_info=_transcript_info(
            transcript=transcript,
            target_text=target_text,
            text_accuracy_applicable=target_text is not None,
            generated_from_audio=(
                mode == ProductMode.PRESENTATION and target_text is None
            ),
        ),
        alignment_evidence=_alignment_evidence(),
        feedback=_build_feedback(word_results),
    )
