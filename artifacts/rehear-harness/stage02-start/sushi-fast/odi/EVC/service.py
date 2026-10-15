# xreal_rehair/evc/service.py

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from openai import OpenAI

from .schema import (
    AudienceState,
    BehaviorCommand,
    ContentScores,
    DeliveryScores,
    EVCUpdateResponse,
    GPTDeliveryScores,
    MtDtEvaluation,
    SegmentEvaluation,
    SlideInfo,
    SpeechMetrics,
    SpeechTextResult,
    SpeechWord,
    UtterancePosition,
    clamp,
)
from .speech2text import speech_to_text_detail


OPENAI_MODEL = os.getenv("OPENAI_EVC_MODEL", "gpt-4.1-nano")
DEBUG_EVC_LOG = os.getenv("DEBUG_EVC_LOG", "true").lower() == "true"
DEBUG_LOG_DIR = Path(os.getenv("EVC_DEBUG_LOG_DIR", "evc_logs"))
UPLOAD_DIR = Path(os.getenv("EVC_UPLOAD_DIR", "evc_uploads"))

client = OpenAI()


SYSTEM_PROMPT = """
당신은 XR 발표 훈련 시스템 Re:hear의 발표 구간 평가기이다.

당신의 역할은 AI 청중의 EVC 상태나 행동을 직접 생성하는 것이 아니다.
당신은 현재 발화 구간을 평가하여 M_t와 D_t 일부를 산출한다.
서버는 당신의 평가값과 음성·시선·슬라이드 지표를 결합하여 EVC와 백채널 행동을 계산한다.

입력에는 다음 정보가 제공된다.
- presentation_title: 발표 제목
- slides_outline: 발표자료의 슬라이드별 요약 목록
- current_slide: 현재 VR에서 열려 있는 슬라이드 정보
- recent_segment_notes: 최근 발표 구간의 짧은 기록
- latest_speech: 이번 구간의 STT 텍스트
- speech_metrics: 서버가 계산한 음성 지표
- utterance_position: 현재 발화 위치

평가해야 하는 내용 평가 M_t는 네 기준으로 구성된다.
organization은 현재 발화가 발표 흐름 안에서 구조적으로 잘 조직되어 있는지를 평가한다.
supporting_material은 근거, 예시, 수치, 사례, 선행연구, 자료 설명이 주장이나 설명을 잘 뒷받침하는지를 평가한다.
central_message는 현재 구간의 핵심 메시지가 명확하게 드러나는지를 평가한다.
cer_validity는 claim, evidence, reasoning의 연결이 타당한지를 평가한다. claim은 주장, evidence는 근거, reasoning은 근거가 주장으로 이어지는 논리이다.

평가해야 하는 전달 평가 D_t 중 당신이 판단할 항목은 두 가지이다.
language_clarity는 문장, 어휘, 용어, 지시어, 반복 표현, 불완전 문장 등을 고려해 청중이 이해하기 쉬운 표현인지 평가한다.
slide_speech_alignment는 현재 발화가 current_slide의 제목, 핵심 문구, 자료 내용과 시간적·의미적으로 잘 맞는지 평가한다.

점수는 모두 -1.0에서 +1.0 사이로 출력한다.
+1.0은 매우 우수, 0.0은 판단 근거 부족 또는 보통, -1.0은 매우 부족을 의미한다.
입력에 없는 정보는 추측하지 말고 missing_inputs에 기록한다.
슬라이드 정보가 비어 있으면 slide_speech_alignment는 0.0에 가깝게 둔다.
latest_speech가 너무 짧거나 의미 단위가 불완전하면 confidence를 낮추고, 점수도 과격하게 주지 않는다.
기존 segment_note를 반복하지 말고, latest_speech에서 새로 확인된 핵심만 한 문장으로 쓴다.
EVC 상태, 행동명, 애니메이션 클립명은 출력하지 않는다.
반드시 response_format 스키마에 맞춰 출력한다.
""".strip()


@dataclass
class EVCSession:
    session_id: str
    presentation_title: str
    slides: list[SlideInfo]
    evc_state: AudienceState
    topic_interest: float
    prior_knowledge: float
    segment_notes: list[str] = field(default_factory=list)
    step: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    slide_file_path: str | None = None


sessions: dict[str, EVCSession] = {}


def normalize_setting(value: str | float | int) -> float:
    if isinstance(value, (float, int)):
        return max(0.0, min(1.0, float(value)))

    text = str(value).strip().lower()
    mapping = {
        "low": 0.25,
        "낮음": 0.25,
        "middle": 0.50,
        "mid": 0.50,
        "medium": 0.50,
        "중간": 0.50,
        "high": 0.75,
        "높음": 0.75,
    }

    if text in mapping:
        return mapping[text]

    try:
        return max(0.0, min(1.0, float(text)))
    except ValueError as e:
        raise ValueError(f"설정값을 해석할 수 없습니다: {value}") from e


def initial_state_from_settings(topic_interest: float, prior_knowledge: float) -> AudienceState:
    initial_e = (topic_interest - 0.5) * 2.0
    initial_c = (prior_knowledge - 0.5) * 2.0
    return AudienceState(E=initial_e, V=0.0, C=initial_c)


async def save_upload_file(upload_file: UploadFile, directory: Path) -> str:
    directory.mkdir(parents=True, exist_ok=True)

    suffix = Path(upload_file.filename or "uploaded_file").suffix
    filename = f"{uuid4()}{suffix}"
    path = directory / filename

    contents = await upload_file.read()
    path.write_bytes(contents)

    return str(path)


async def create_smart_session(
    presentation_title: str,
    topic_interest: str,
    prior_knowledge: str,
    slide_file: UploadFile | None = None,
) -> EVCSession:
    topic_value = normalize_setting(topic_interest)
    knowledge_value = normalize_setting(prior_knowledge)

    slide_file_path = None
    slides: list[SlideInfo] = []

    if slide_file is not None:
        slide_file_path = await save_upload_file(slide_file, UPLOAD_DIR)
        slides = extract_slides_from_file(slide_file_path)

    session_id = str(uuid4())
    session = EVCSession(
        session_id=session_id,
        presentation_title=presentation_title,
        slides=slides,
        evc_state=initial_state_from_settings(topic_value, knowledge_value),
        topic_interest=topic_value,
        prior_knowledge=knowledge_value,
        slide_file_path=slide_file_path,
    )

    sessions[session_id] = session
    return session


def extract_slides_from_file(file_path: str) -> list[SlideInfo]:
    path = Path(file_path)

    if path.suffix.lower() == ".pdf":
        return extract_pdf_pages(path)

    if path.suffix.lower() in {".pptx", ".ppt"}:
        return [
            SlideInfo(
                index=0,
                title=path.name,
                text="PPTX 텍스트 추출은 아직 구현되지 않았습니다.",
                summary="PPTX 자료가 업로드되었으나 현재 프로토타입에서는 슬라이드 텍스트를 추출하지 않습니다.",
            )
        ]

    return [
        SlideInfo(
            index=0,
            title=path.name,
            text="지원되지 않는 발표자료 형식입니다.",
            summary="발표자료가 업로드되었으나 텍스트 추출을 수행하지 않았습니다.",
        )
    ]


def extract_pdf_pages(path: Path) -> list[SlideInfo]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return [
            SlideInfo(
                index=0,
                title=path.name,
                text="pypdf가 설치되어 있지 않아 PDF 텍스트를 추출하지 못했습니다.",
                summary="PDF 자료가 업로드되었으나 텍스트 추출이 비활성화되었습니다.",
            )
        ]

    reader = PdfReader(str(path))
    slides: list[SlideInfo] = []

    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        clean_text = normalize_space(text)
        title = clean_text[:50] if clean_text else f"Slide {index + 1}"
        summary = clean_text[:300] if clean_text else ""

        slides.append(
            SlideInfo(
                index=index,
                title=title,
                text=clean_text[:2500],
                summary=summary,
            )
        )

    return slides


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def get_session(session_id: str) -> EVCSession:
    session = sessions.get(session_id)
    if session is None:
        raise ValueError(f"존재하지 않는 session_id입니다: {session_id}")
    return session


async def save_audio_temp(audio: UploadFile) -> str:
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        contents = await audio.read()
        temp_file.write(contents)
        return temp_file.name


def get_slide_context(session: EVCSession, current_slide_index: int) -> dict:
    if not session.slides:
        return {
            "slides_outline": [],
            "current_slide": None,
            "nearby_slides": [],
        }

    current_index = max(0, min(current_slide_index, len(session.slides) - 1))
    current_slide = session.slides[current_index]

    nearby = [
        slide
        for slide in session.slides
        if abs(slide.index - current_index) <= 1
    ]

    return {
        "slides_outline": [
            {
                "index": slide.index,
                "title": slide.title,
                "summary": slide.summary[:300],
            }
            for slide in session.slides
        ],
        "current_slide": current_slide.model_dump(),
        "nearby_slides": [slide.model_dump() for slide in nearby],
    }


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

    pauses: list[float] = []
    for previous, current in zip(words, words[1:]):
        gap = current.start - previous.end
        if gap >= 0.7:
            pauses.append(gap)

    filler_words = {"어", "음", "그", "저", "아", "뭐", "그러니까", "약간"}
    filler_count = sum(1 for word in words if word.word.strip().lower() in filler_words)

    repeated_word_count = 0
    for previous, current in zip(words, words[1:]):
        if previous.word == current.word:
            repeated_word_count += 1

    avg_confidence = sum(word.confidence for word in words) / word_count
    vocal_score = compute_vocal_delivery_score(
        speech_rate_wps=speech_rate_wps,
        pause_count=len(pauses),
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
    speech_rate_wps: float,
    pause_count: int,
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
    if pause_ratio > 0.35:
        score -= 0.30
    elif pause_ratio > 0.20:
        score -= 0.15
    else:
        score += 0.10

    filler_ratio = filler_count / max(1, word_count)
    if filler_ratio > 0.15:
        score -= 0.30
    elif filler_ratio > 0.07:
        score -= 0.15
    else:
        score += 0.10

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


def build_gpt_payload(
    session: EVCSession,
    latest_speech: str,
    speech_metrics: SpeechMetrics,
    current_slide_index: int,
    utterance_position: UtterancePosition,
) -> dict:
    slide_context = get_slide_context(session, current_slide_index)

    return {
        "presentation_title": session.presentation_title,
        "slides_outline": slide_context["slides_outline"],
        "current_slide": slide_context["current_slide"],
        "nearby_slides": slide_context["nearby_slides"],
        "recent_segment_notes": session.segment_notes[-8:],
        "latest_speech": latest_speech,
        "speech_metrics": speech_metrics.model_dump(),
        "utterance_position": utterance_position,
    }


def call_gpt_for_segment_evaluation(
    session: EVCSession,
    latest_speech: str,
    speech_metrics: SpeechMetrics,
    current_slide_index: int,
    utterance_position: UtterancePosition,
) -> SegmentEvaluation:
    payload = build_gpt_payload(
        session=session,
        latest_speech=latest_speech,
        speech_metrics=speech_metrics,
        current_slide_index=current_slide_index,
        utterance_position=utterance_position,
    )

    completion = client.chat.completions.parse(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        response_format=SegmentEvaluation,
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("GPT 평가 결과를 SegmentEvaluation으로 파싱하지 못했습니다.")

    return parsed


def assemble_mt_dt(
    gpt_eval: SegmentEvaluation,
    speech_metrics: SpeechMetrics,
    gaze_delivery_score: float | None = None,
) -> MtDtEvaluation:
    gaze_score = 0.0 if gaze_delivery_score is None else clamp(gaze_delivery_score)

    delivery = DeliveryScores(
        language_clarity=gpt_eval.delivery.language_clarity,
        vocal_delivery=speech_metrics.vocal_delivery_score,
        gaze_delivery=gaze_score,
        slide_speech_alignment=gpt_eval.delivery.slide_speech_alignment,
    )

    return MtDtEvaluation(
        move=gpt_eval.move,
        content=gpt_eval.content,
        delivery=delivery,
        segment_note=gpt_eval.segment_note,
        short_reason=gpt_eval.short_reason,
        missing_inputs=gpt_eval.missing_inputs,
        confidence=gpt_eval.confidence,
    )


def compute_evc_target(evaluation: MtDtEvaluation) -> AudienceState:
    org = evaluation.content.organization
    sup = evaluation.content.supporting_material
    msg = evaluation.content.central_message
    cer = evaluation.content.cer_validity

    lang = evaluation.delivery.language_clarity
    voc = evaluation.delivery.vocal_delivery
    gaze = evaluation.delivery.gaze_delivery
    align = evaluation.delivery.slide_speech_alignment

    delta_e_m = clamp(0.50 * org + 0.50 * msg)
    delta_v_m = clamp(1.00 * sup + 1.00 * cer)
    delta_c_m = clamp(1.00 * org + 0.50 * sup + 1.00 * msg + 0.50 * cer)

    delta_e_d = clamp(0.50 * lang + 1.00 * voc + 1.00 * gaze)
    delta_v_d = clamp(0.50 * voc + 0.50 * gaze + 0.50 * align)
    delta_c_d = clamp(1.00 * lang + 1.00 * align)

    e = clamp(0.45 * delta_e_m + 0.55 * delta_e_d)
    v = clamp(0.55 * delta_v_m + 0.45 * delta_v_d)
    c = clamp(0.50 * delta_c_m + 0.50 * delta_c_d)

    return AudienceState(E=e, V=v, C=c)


def apply_evc_update(
    previous: AudienceState,
    target: AudienceState,
    topic_interest: float,
    prior_knowledge: float,
) -> AudienceState:
    next_e = move_toward(previous.E, target.E, up_rate=0.35, down_rate=0.55)
    next_v = move_toward(previous.V, target.V, up_rate=0.35, down_rate=0.45)
    next_c = move_toward(previous.C, target.C, up_rate=0.35, down_rate=0.55)

    engagement_sensitivity = sensitivity_for_negative_change(topic_interest)
    clarity_sensitivity = sensitivity_for_negative_change(prior_knowledge)

    if next_e < previous.E:
        next_e = previous.E + (next_e - previous.E) * engagement_sensitivity

    if next_c < previous.C:
        next_c = previous.C + (next_c - previous.C) * clarity_sensitivity

    return AudienceState(E=next_e, V=next_v, C=next_c)


def move_toward(current: float, target: float, up_rate: float, down_rate: float) -> float:
    rate = down_rate if target < current else up_rate
    return clamp(current + (target - current) * rate)


def sensitivity_for_negative_change(setting_value: float) -> float:
    if setting_value <= 0.33:
        return 1.20
    if setting_value >= 0.67:
        return 0.80
    return 1.00


def level(value: float) -> str:
    if value < -0.34:
        return "low"
    if value > 0.33:
        return "high"
    return "mid"


def generate_behavior(state: AudienceState, utterance_position: UtterancePosition) -> BehaviorCommand:
    levels = {
        "E": level(state.E),
        "V": level(state.V),
        "C": level(state.C),
    }

    if levels["E"] == "mid" and levels["V"] == "mid" and levels["C"] == "mid":
        return BehaviorCommand(
            selected_behavior_id="BL_01",
            group="Baseline Listening",
            action_overlay=None,
            gaze_head_adjustment="speaker_gaze_neutral",
            intensity=0.3,
        )

    abs_values = {
        "E": abs(state.E),
        "V": abs(state.V),
        "C": abs(state.C),
    }

    dominant = choose_dominant_axis(state, abs_values)

    if dominant == "E":
        if state.E >= 0:
            return BehaviorCommand(
                selected_behavior_id="AL_01",
                group="Attentive Listening",
                gaze_head_adjustment="stable_speaker_gaze",
                intensity=min(1.0, abs(state.E)),
            )
        return BehaviorCommand(
            selected_behavior_id="AL_05",
            group="Attentional Withdrawal",
            gaze_head_adjustment="reduced_speaker_gaze",
            intensity=min(1.0, abs(state.E)),
        )

    if dominant == "V":
        if state.V >= 0:
            return BehaviorCommand(
                selected_behavior_id="EM_01",
                group="Positive Evaluative Monitoring",
                gaze_head_adjustment="stable_speaker_gaze",
                intensity=min(1.0, abs(state.V)),
            )
        return BehaviorCommand(
            selected_behavior_id="EM_05",
            group="Negative Evaluative Monitoring",
            gaze_head_adjustment="skeptical_speaker_gaze",
            intensity=min(1.0, abs(state.V)),
        )

    if state.C >= 0:
        return BehaviorCommand(
            selected_behavior_id="CT_01",
            group="Clear Comprehension Tracking",
            gaze_head_adjustment="speaker_slide_tracking",
            intensity=min(1.0, abs(state.C)),
        )

    return BehaviorCommand(
        selected_behavior_id="CT_05",
        group="Confused Comprehension Tracking",
        gaze_head_adjustment="slide_recheck",
        intensity=min(1.0, abs(state.C)),
    )


def choose_dominant_axis(state: AudienceState, abs_values: dict[str, float]) -> str:
    max_axis = max(abs_values, key=abs_values.get)
    max_value = abs_values[max_axis]

    near_axes = [
        axis
        for axis, value in abs_values.items()
        if max_value - value <= 0.10
    ]

    if "C" in near_axes and state.C < -0.33:
        return "C"

    if "V" in near_axes:
        return "V"

    if "C" in near_axes and state.C > 0.33:
        return "C"

    if "E" in near_axes:
        return "E"

    return max_axis


async def update_evc_from_audio(
    session_id: str,
    audio: UploadFile,
    current_slide_index: int = 0,
    utterance_position: UtterancePosition = "during_speech",
    language: str = "ko-KR",
    gaze_delivery_score: float | None = None,
) -> EVCUpdateResponse:
    session = get_session(session_id)
    temp_audio_path = await save_audio_temp(audio)

    try:
        stt_result = speech_to_text_detail(temp_audio_path, language=language)
        speech_metrics = compute_speech_metrics(stt_result)

        if not stt_result.transcript.strip():
            behavior = generate_behavior(session.evc_state, utterance_position)
            return EVCUpdateResponse(
                session_id=session.session_id,
                step=session.step,
                latest_speech="",
                current_slide_index=current_slide_index,
                speech_metrics=speech_metrics,
                evaluation=empty_evaluation(),
                evc_state=session.evc_state,
                behavior=behavior,
            )

        gpt_eval = call_gpt_for_segment_evaluation(
            session=session,
            latest_speech=stt_result.transcript,
            speech_metrics=speech_metrics,
            current_slide_index=current_slide_index,
            utterance_position=utterance_position,
        )

        evaluation = assemble_mt_dt(
            gpt_eval=gpt_eval,
            speech_metrics=speech_metrics,
            gaze_delivery_score=gaze_delivery_score,
        )

        target_state = compute_evc_target(evaluation)
        next_state = apply_evc_update(
            previous=session.evc_state,
            target=target_state,
            topic_interest=session.topic_interest,
            prior_knowledge=session.prior_knowledge,
        )

        session.evc_state = next_state
        session.step += 1
        session.updated_at = datetime.now()

        if evaluation.segment_note.strip():
            session.segment_notes.append(evaluation.segment_note.strip())

        behavior = generate_behavior(next_state, utterance_position)

        response = EVCUpdateResponse(
            session_id=session.session_id,
            step=session.step,
            latest_speech=stt_result.transcript,
            current_slide_index=current_slide_index,
            speech_metrics=speech_metrics,
            evaluation=evaluation,
            evc_state=next_state,
            behavior=behavior,
        )

        debug_save_step(session, response, target_state)
        return response

    finally:
        try:
            os.remove(temp_audio_path)
        except OSError:
            pass


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
        short_reason="발화 텍스트가 비어 있어 평가하지 않음.",
        missing_inputs=["latest_speech"],
        confidence=0.0,
    )


def debug_save_step(session: EVCSession, response: EVCUpdateResponse, target_state: AudienceState) -> None:
    if not DEBUG_EVC_LOG:
        return

    session_dir = DEBUG_LOG_DIR / session.session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "session_id": session.session_id,
        "step": session.step,
        "created_at": datetime.now().isoformat(),
        "target_state": target_state.model_dump(),
        "response": response.model_dump(),
    }

    path = session_dir / f"step_{session.step:04d}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")