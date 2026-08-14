# xreal_rehair/evc/schema.py

import math
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

StateLevel = Literal["low", "mid", "high"]
DominantAxis = Literal["E", "V", "C"]
Direction = Literal["positive", "negative"]
AudienceGroup = Literal[
    "Baseline Listening",
    "Attentive Listening",
    "Evaluative Monitoring",
    "Comprehension Tracking",
]
OutputLayer = Literal["Face", "Body", "GazeHead"]
BlendMode = Literal["override", "additive"]
MotionClass = Literal["stable", "transient"]
AudienceRow = Literal["front", "middle", "rear"]
AudienceSeat = Literal["left", "right"]
EventName = Literal[
    "information_dense",
    "slide_reference",
    "repeated_disengagement",
    "low_arousal",
    "long_static_posture",
    "tension",
    "nearby_interaction",
]


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ensure_finite(value: float, field_name: str = "value") -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


class AudienceState(BaseModel):
    E: float = Field(description="-1~1, Engagement")
    V: float = Field(description="-1~1, Evaluative Valence")
    C: float = Field(description="-1~1, Cognitive Clarity")

    @field_validator("E", "V", "C")
    @classmethod
    def clamp_state(cls, value: float) -> float:
        return clamp(ensure_finite(value, "audience state"))


class ContentScores(BaseModel):
    organization: float = Field(description="-1~1, Organization")
    supporting_material: float = Field(description="-1~1, Supporting Material")
    central_message: float = Field(description="-1~1, Central Message")
    cer_validity: float = Field(description="-1~1, Claim-Evidence-Reasoning Validity")

    @field_validator("organization", "supporting_material", "central_message", "cer_validity")
    @classmethod
    def clamp_scores(cls, value: float) -> float:
        return clamp(ensure_finite(value, "content score"))


class GPTDeliveryScores(BaseModel):
    language_clarity: float = Field(description="-1~1, Language Clarity")
    slide_speech_alignment: float = Field(description="-1~1, Slide-Speech Alignment")

    @field_validator("language_clarity", "slide_speech_alignment")
    @classmethod
    def clamp_scores(cls, value: float) -> float:
        return clamp(ensure_finite(value, "GPT delivery score"))


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
        return max(0.0, min(1.0, ensure_finite(value, "confidence")))


class DeliveryScores(BaseModel):
    language_clarity: float
    vocal_delivery: float
    gaze_delivery: float
    slide_speech_alignment: float

    @field_validator("language_clarity", "vocal_delivery", "gaze_delivery", "slide_speech_alignment")
    @classmethod
    def clamp_scores(cls, value: float) -> float:
        return clamp(ensure_finite(value, "delivery score"))


class MtDtEvaluation(BaseModel):
    move: MoveType
    content: ContentScores
    delivery: DeliveryScores
    segment_note: str
    short_reason: str
    missing_inputs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    @field_validator("confidence")
    @classmethod
    def finite_confidence(cls, value: float) -> float:
        return ensure_finite(value, "evaluation confidence")


class SpeechWord(BaseModel):
    word: str
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("start", "end", "confidence")
    @classmethod
    def finite_word_number(cls, value: float) -> float:
        return ensure_finite(value, "speech word number")

    @model_validator(mode="after")
    def end_is_not_before_start(self) -> "SpeechWord":
        if self.end < self.start:
            raise ValueError("speech word end cannot be before start")
        return self


class SpeechTextResult(BaseModel):
    transcript: str
    words: list[SpeechWord] = Field(default_factory=list)


class SpeechMetrics(BaseModel):
    duration_s: float = Field(ge=0.0)
    word_count: int = Field(ge=0)
    speech_rate_wps: float = Field(ge=0.0)
    pause_count: int = Field(ge=0)
    pause_total_s: float = Field(ge=0.0)
    filler_count: int = Field(ge=0)
    repeated_word_count: int = Field(ge=0)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    vocal_delivery_score: float = Field(ge=-1.0, le=1.0)

    @field_validator(
        "duration_s",
        "speech_rate_wps",
        "pause_total_s",
        "avg_confidence",
        "vocal_delivery_score",
    )
    @classmethod
    def finite_metric(cls, value: float) -> float:
        return ensure_finite(value, "speech metric")


class SlideInfo(BaseModel):
    index: int = Field(ge=0)
    title: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=2500)
    summary: str = Field(default="", max_length=300)


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


class StrictModel(BaseModel):
    """Base model for the v2 contract; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ChannelPreference(StrictModel):
    face: float = Field(alias="Face", ge=0.0, le=1.0)
    body: float = Field(alias="Body", ge=0.0, le=1.0)
    gaze_head: float = Field(alias="GazeHead", ge=0.0, le=1.0)

    @field_validator("face", "body", "gaze_head")
    @classmethod
    def finite_weight(cls, value: float) -> float:
        return ensure_finite(value, "channel preference")

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "ChannelPreference":
        total = self.face + self.body + self.gaze_head
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError("channel preference weights must sum to 1.0")
        return self


class AudienceProfile(StrictModel):
    row: AudienceRow
    seat: AudienceSeat
    has_laptop: bool
    responsiveness: float = Field(ge=0.40, le=0.75)
    expressivity: float = Field(ge=0.30, le=0.70)
    critical_bias: float = Field(ge=0.25, le=0.75)
    channel_preference: ChannelPreference

    @field_validator("responsiveness", "expressivity", "critical_bias")
    @classmethod
    def finite_trait(cls, value: float) -> float:
        return ensure_finite(value, "audience behavior trait")


class StateSensitivity(StrictModel):
    E: float = Field(ge=0.8, le=1.2)
    V: float = Field(ge=0.8, le=1.2)
    C: float = Field(ge=0.8, le=1.2)

    @field_validator("E", "V", "C")
    @classmethod
    def finite_sensitivity(cls, value: float) -> float:
        return ensure_finite(value, "state sensitivity")


class AudienceSnapshot(StrictModel):
    agent_id: str = Field(pattern=r"^audience_0[1-6]$")
    profile: AudienceProfile
    state: AudienceState


class BehaviorHistoryEntry(StrictModel):
    behavior_id: str = Field(min_length=1, max_length=64)
    variation_id: str = Field(min_length=3, max_length=128)
    start_time: float = Field(ge=0.0)

    @field_validator("start_time")
    @classmethod
    def finite_start_time(cls, value: float) -> float:
        return ensure_finite(value, "history start time")


class AudienceRuntimeState(StrictModel):
    agent_id: str = Field(pattern=r"^audience_0[1-6]$")
    profile: AudienceProfile
    state: AudienceState
    previous_dominant_axis: DominantAxis | None = None
    core_history: list[BehaviorHistoryEntry] = Field(default_factory=list, max_length=8)
    action_history: list[BehaviorHistoryEntry] = Field(default_factory=list, max_length=8)
    cooldowns: dict[str, float] = Field(default_factory=dict)
    consecutive_low_engagement: int = Field(default=0, ge=0)
    consecutive_low_arousal: int = Field(default=0, ge=0)
    last_body_command_time: float = Field(default=0.0, ge=0.0)

    @field_validator("cooldowns")
    @classmethod
    def validate_cooldowns(cls, value: dict[str, float]) -> dict[str, float]:
        for variation_id, used_at in value.items():
            if not variation_id or ensure_finite(used_at, "cooldown timestamp") < 0:
                raise ValueError("cooldown entries require a variation id and non-negative time")
        return value


class EventSignals(StrictModel):
    information_dense: float = Field(default=0.0, ge=0.0, le=1.0)
    slide_reference: float = Field(default=0.0, ge=0.0, le=1.0)
    repeated_disengagement: float = Field(default=0.0, ge=0.0, le=1.0)
    low_arousal: float = Field(default=0.0, ge=0.0, le=1.0)
    long_static_posture: float = Field(default=0.0, ge=0.0, le=1.0)
    tension: float = Field(default=0.0, ge=0.0, le=1.0)
    nearby_interaction: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator(
        "information_dense",
        "slide_reference",
        "repeated_disengagement",
        "low_arousal",
        "long_static_posture",
        "tension",
        "nearby_interaction",
    )
    @classmethod
    def finite_strength(cls, value: float) -> float:
        return ensure_finite(value, "event strength")


class SegmentContext(StrictModel):
    current_slide_index: int = Field(default=0, ge=0)
    utterance_position: UtterancePosition = "during_speech"
    language: str = Field(default="ko-KR", min_length=2, max_length=35)
    gaze_delivery_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    slide_reference: bool = False
    event_signals: EventSignals = Field(default_factory=EventSignals)
    client_time_s: float = Field(ge=0.0)

    @field_validator("gaze_delivery_score", "client_time_s")
    @classmethod
    def finite_context_number(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return ensure_finite(value, "segment context number")


class StateCondition(StrictModel):
    E: set[StateLevel] | None = None
    V: set[StateLevel] | None = None
    C: set[StateLevel] | None = None
    dominant_axis: DominantAxis | None = None
    direction: Direction | None = None

    @model_validator(mode="after")
    def not_empty_when_present(self) -> "StateCondition":
        for levels in (self.E, self.V, self.C):
            if levels is not None and not levels:
                raise ValueError("state level sets cannot be empty")
        return self


class SceneGate(StrictModel):
    requires_laptop: bool = False
    allowed_agents: set[str] | None = None
    allowed_rows: set[AudienceRow] | None = None

    @field_validator("allowed_agents")
    @classmethod
    def valid_agent_ids(cls, value: set[str] | None) -> set[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("allowed_agents cannot be empty")
        valid = {f"audience_{index:02d}" for index in range(1, 7)}
        if not value <= valid:
            raise ValueError("allowed_agents contains an unknown audience id")
        return value


class UnityActionSpec(StrictModel):
    layer: OutputLayer
    action_id: str = Field(pattern=r"^(face|body|gaze_head)\.[a-z0-9_]+$")
    duration: float = Field(gt=0.0, le=60.0)
    blend_mode: BlendMode = "override"

    @field_validator("duration")
    @classmethod
    def finite_duration(cls, value: float) -> float:
        return ensure_finite(value, "Unity action duration")

    @model_validator(mode="after")
    def action_namespace_matches_layer(self) -> "UnityActionSpec":
        namespace = {
            "Face": "face.",
            "Body": "body.",
            "GazeHead": "gaze_head.",
        }[self.layer]
        if not self.action_id.startswith(namespace):
            raise ValueError("action_id namespace must match its output layer")
        return self


class CoreClipSpec(StrictModel):
    behavior_id: str = Field(pattern=r"^(BL|AL|EM|CT)_[0-9]{2}$")
    variation_id: str = Field(pattern=r"^(BL|AL|EM|CT)_[0-9]{2}\.[a-z0-9_]+$")
    parent_group: AudienceGroup
    trigger_conditions: list[StateCondition] = Field(min_length=1)
    utterance_positions: set[UtterancePosition]
    requires_slide_reference: bool = False
    channels: set[OutputLayer]
    cooldown_s: float = Field(ge=0.0, le=300.0)
    expressivity_target: float = Field(ge=0.0, le=1.0)
    motion_class: MotionClass
    critical: bool = False
    unity_actions: list[UnityActionSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_core_clip(self) -> "CoreClipSpec":
        if not self.variation_id.startswith(f"{self.behavior_id}."):
            raise ValueError("variation_id must be namespaced by behavior_id")
        if not self.utterance_positions or not self.channels:
            raise ValueError("clip positions and channels cannot be empty")
        mapped_layers = {action.layer for action in self.unity_actions}
        if mapped_layers != self.channels:
            raise ValueError("clip channels must exactly match Unity action layers")
        return self


class ActionClipSpec(StrictModel):
    behavior_id: str = Field(pattern=r"^ACT_[0-9]{2}$")
    variation_id: str = Field(pattern=r"^ACT_[0-9]{2}\.[a-z0-9_]+$")
    event_triggers: set[EventName]
    state_gates: list[StateCondition] = Field(default_factory=list)
    utterance_positions: set[UtterancePosition]
    requires_slide_reference: bool = False
    scene_gate: SceneGate = Field(default_factory=SceneGate)
    channels: set[OutputLayer]
    cooldown_s: float = Field(ge=0.0, le=300.0)
    expressivity_target: float = Field(ge=0.0, le=1.0)
    unity_actions: list[UnityActionSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_action_clip(self) -> "ActionClipSpec":
        if not self.variation_id.startswith(f"{self.behavior_id}."):
            raise ValueError("variation_id must be namespaced by behavior_id")
        if not self.event_triggers or not self.utterance_positions or not self.channels:
            raise ValueError("action events, positions, and channels cannot be empty")
        mapped_layers = {action.layer for action in self.unity_actions}
        if mapped_layers != self.channels:
            raise ValueError("action channels must exactly match Unity action layers")
        return self


class ClipPoolCatalog(StrictModel):
    core: list[CoreClipSpec]
    actions: list[ActionClipSpec]

    @model_validator(mode="after")
    def variation_ids_are_globally_unique(self) -> "ClipPoolCatalog":
        ids = [clip.variation_id for clip in self.core]
        ids.extend(clip.variation_id for clip in self.actions)
        if len(ids) != len(set(ids)):
            raise ValueError("clip variation_id values must be globally unique")
        return self


class BehaviorChoice(StrictModel):
    behavior_id: str = Field(min_length=1, max_length=64)
    variation_id: str = Field(min_length=3, max_length=128)
    probability: float = Field(ge=0.0, le=1.0)

    @field_validator("probability")
    @classmethod
    def finite_probability(cls, value: float) -> float:
        return ensure_finite(value, "selection probability")


class UnityCommand(StrictModel):
    agent_id: str = Field(pattern=r"^audience_0[1-6]$")
    start_time: float = Field(ge=0.0)
    layer: OutputLayer
    action_id: str = Field(pattern=r"^(face|body|gaze_head)\.[a-z0-9_]+$")
    duration: float = Field(gt=0.0, le=60.0)
    sync_group: UUID
    selected_behavior_id: str = Field(min_length=1, max_length=64)
    selected_variation_id: str = Field(min_length=3, max_length=128)
    priority: int = Field(ge=0, le=255)
    blend_mode: BlendMode
    intensity: float = Field(ge=0.0, le=1.0)

    @field_validator("start_time", "duration", "intensity")
    @classmethod
    def finite_command_number(cls, value: float) -> float:
        return ensure_finite(value, "Unity command number")


class AudienceDecision(StrictModel):
    agent_id: str = Field(pattern=r"^audience_0[1-6]$")
    previous_state: AudienceState
    sensitivity: StateSensitivity
    state: AudienceState
    dominant_axis: DominantAxis | None
    direction: Direction | None
    core_behavior: BehaviorChoice | None
    action_overlay: BehaviorChoice | None
    no_op_reason: str | None = Field(default=None, max_length=128)


class StateDeltaBreakdown(StrictModel):
    content: AudienceState
    delivery: AudienceState
    common: AudienceState


class SmartStartOptions(StrictModel):
    presentation_title: str = Field(min_length=1, max_length=200)
    topic_interest: Literal[0.25, 0.5, 0.75] = 0.5
    prior_knowledge: Literal[0.25, 0.5, 0.75] = 0.5
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)

    @field_validator("presentation_title")
    @classmethod
    def title_is_not_whitespace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("presentation_title cannot be blank")
        return stripped


class UpdateRequestMetadata(StrictModel):
    session_id: UUID
    request_id: UUID
    expected_step: int = Field(ge=0)
    context: SegmentContext


class SmartStartResponseV2(StrictModel):
    api_version: Literal["2.0"] = "2.0"
    session_id: UUID
    session_token: str = Field(min_length=32)
    seed: int = Field(ge=0, le=2_147_483_647)
    presentation_title: str = Field(min_length=1, max_length=200)
    initial_evc_state: AudienceState
    topic_interest: float
    prior_knowledge: float
    audiences: list[AudienceSnapshot] = Field(min_length=6, max_length=6)
    step: Literal[0] = 0
    expires_in_s: int = Field(gt=0)
    slide_count: int = Field(ge=0)
    slides: list[SlideInfo]

    @model_validator(mode="after")
    def audience_ids_are_unique(self) -> "SmartStartResponseV2":
        ids = [audience.agent_id for audience in self.audiences]
        if len(ids) != len(set(ids)):
            raise ValueError("audience agent_id values must be unique")
        return self


class SessionResponseV2(StrictModel):
    api_version: Literal["2.0"] = "2.0"
    session_id: UUID
    presentation_title: str
    evc_state: AudienceState
    audiences: list[AudienceSnapshot] = Field(min_length=6, max_length=6)
    step: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    expires_in_s: int = Field(ge=0)
    topic_interest: float
    prior_knowledge: float
    segment_notes: list[str]
    slide_count: int = Field(ge=0)
    slides: list[SlideInfo]
    warnings: list[str] = Field(default_factory=list)


class EVCUpdateResponseV2(StrictModel):
    api_version: Literal["2.0"] = "2.0"
    request_id: UUID
    session_id: UUID
    step: int = Field(ge=0)
    accepted_client_time_s: float = Field(ge=0.0)
    latest_speech: str
    current_slide_index: int = Field(ge=0)
    speech_metrics: SpeechMetrics
    evaluation: MtDtEvaluation
    delta: StateDeltaBreakdown
    evc_state: AudienceState
    behavior: BehaviorCommand | None
    audiences: list[AudienceDecision] = Field(min_length=6, max_length=6)
    commands: list[UnityCommand]
    warnings: list[str] = Field(default_factory=list)
    no_op_reason: str | None = Field(default=None, max_length=128)
    diagnostics: dict | None = None

    @field_validator("accepted_client_time_s")
    @classmethod
    def finite_accepted_time(cls, value: float) -> float:
        return ensure_finite(value, "accepted client time")
