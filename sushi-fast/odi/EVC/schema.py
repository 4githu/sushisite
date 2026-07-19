# xreal_rehair/evc/schema.py

from typing import Literal
from pydantic import BaseModel, Field, field_validator


MoveType = Literal[
    "Orientation",
    "Rationale",
    "Framework",
    "Purpose",
    "Methods",
    "Results",
    "Implication",
    "Termination",
    "Unknown",
]

UtterancePosition = Literal[
    "during_speech",
    "utterance_boundary",
    "silence_or_pause",
    "slide_transition",
]


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class AudienceState(BaseModel):
    E: float = Field(description="-1~1, Engagement")
    V: float = Field(description="-1~1, Evaluative Valence")
    C: float = Field(description="-1~1, Cognitive Clarity")

    @field_validator("E", "V", "C")
    @classmethod
    def clamp_state(cls, value: float) -> float:
        return clamp(value)


class ContentScores(BaseModel):
    organization: float = Field(description="-1~1, Organization")
    supporting_material: float = Field(description="-1~1, Supporting Material")
    central_message: float = Field(description="-1~1, Central Message")
    cer_validity: float = Field(description="-1~1, Claim-Evidence-Reasoning Validity")

    @field_validator("organization", "supporting_material", "central_message", "cer_validity")
    @classmethod
    def clamp_scores(cls, value: float) -> float:
        return clamp(value)


class GPTDeliveryScores(BaseModel):
    language_clarity: float = Field(description="-1~1, Language Clarity")
    slide_speech_alignment: float = Field(description="-1~1, Slide-Speech Alignment")

    @field_validator("language_clarity", "slide_speech_alignment")
    @classmethod
    def clamp_scores(cls, value: float) -> float:
        return clamp(value)


class SegmentEvaluation(BaseModel):
    move: MoveType
    content: ContentScores
    delivery: GPTDeliveryScores
    segment_note: str = Field(description="이번 구간의 핵심 내용. 기존 요약 반복 금지.")
    short_reason: str = Field(description="평가 근거를 짧게 설명.")
    missing_inputs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, description="0~1, 평가 신뢰도")

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class DeliveryScores(BaseModel):
    language_clarity: float
    vocal_delivery: float
    gaze_delivery: float
    slide_speech_alignment: float

    @field_validator("language_clarity", "vocal_delivery", "gaze_delivery", "slide_speech_alignment")
    @classmethod
    def clamp_scores(cls, value: float) -> float:
        return clamp(value)


class MtDtEvaluation(BaseModel):
    move: MoveType
    content: ContentScores
    delivery: DeliveryScores
    segment_note: str
    short_reason: str
    missing_inputs: list[str] = Field(default_factory=list)
    confidence: float = 0.7


class SpeechWord(BaseModel):
    word: str
    start: float
    end: float
    confidence: float = 0.0


class SpeechTextResult(BaseModel):
    transcript: str
    words: list[SpeechWord] = Field(default_factory=list)


class SpeechMetrics(BaseModel):
    duration_s: float
    word_count: int
    speech_rate_wps: float
    pause_count: int
    pause_total_s: float
    filler_count: int
    repeated_word_count: int
    avg_confidence: float
    vocal_delivery_score: float


class SlideInfo(BaseModel):
    index: int
    title: str = ""
    text: str = ""
    summary: str = ""


class BehaviorCommand(BaseModel):
    selected_behavior_id: str
    group: str
    action_overlay: str | None = None
    gaze_head_adjustment: str | None = None
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)


class EVCUpdateResponse(BaseModel):
    session_id: str
    step: int
    latest_speech: str
    current_slide_index: int
    speech_metrics: SpeechMetrics
    evaluation: MtDtEvaluation
    evc_state: AudienceState
    behavior: BehaviorCommand