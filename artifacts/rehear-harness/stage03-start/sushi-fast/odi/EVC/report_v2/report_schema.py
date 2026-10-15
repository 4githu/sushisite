from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, Field, model_validator

from .report_metric_catalog import CONTENT_METRIC_SPECS, DELIVERY_METRIC_SPECS

from ..schema import (
    AudienceDecision,
    AudienceState,
    MtDtEvaluation,
    SegmentContext,
    SpeechMetrics,
    StateDeltaBreakdown,
    StrictModel,
    UnityCommand,
)


class ReportSegmentRecord(StrictModel):
    step: int = Field(ge=1)
    client_time_s: float = Field(ge=0.0)
    slide_index: int = Field(ge=0)
    transcript: str = Field(min_length=1)
    evaluation: MtDtEvaluation
    speech_metrics: SpeechMetrics
    evc_state: AudienceState
    context: SegmentContext | None = None
    delta: StateDeltaBreakdown | None = None
    audiences: list[AudienceDecision] = Field(default_factory=list)
    commands: list[UnityCommand] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReportReactionRecord(StrictModel):
    """A reaction-clock result linked back to the analysis steps it consumed."""

    sequence: int = Field(ge=1)
    client_time_s: float = Field(ge=0.0)
    source_steps: list[int] = Field(default_factory=list)
    audiences: list[AudienceDecision] = Field(default_factory=list)
    commands: list[UnityCommand] = Field(default_factory=list)


class ReportEvidence(StrictModel):
    evidence_id: str = Field(pattern=r"^segment-[1-9][0-9]*$")
    source_step: int = Field(ge=1)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    slide: int = Field(ge=1)
    transcript_excerpt: str
    evaluation_summary: str
    metric_impacts: dict[Literal["engagement", "clarity", "credibility"], float]
    confidence: float = Field(ge=0.0, le=1.0)
    missing_inputs: list[str] = Field(default_factory=list)


class ReportReactionTrace(StrictModel):
    reaction_id: str = Field(pattern=r"^reaction-[1-9][0-9]*$")
    sequence: int = Field(ge=1)
    time_sec: float = Field(ge=0.0)
    source_steps: list[int] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    audiences: list[AudienceDecision] = Field(default_factory=list)
    commands: list[UnityCommand] = Field(default_factory=list)


class ReportGenerationMetadata(StrictModel):
    generated_at: datetime
    generator: str
    source_segment_count: int = Field(ge=0)
    source_reaction_count: int = Field(default=0, ge=0)
    transcript_word_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    stt_provider: Literal["deepgram", "azure"] | None = None


class ReportScore(StrictModel):
    overall_score: int = Field(ge=0, le=100)
    percentile: int | None = Field(default=None, ge=0, le=100)
    grade: str
    # Accepted when loading an older V2 record, but no longer persisted. The
    # current comparison is returned beside the session at read time.
    previous_session_delta: int | None = Field(default=None, exclude=True)


class ReportDuration(StrictModel):
    planned_seconds: int = Field(ge=0)
    actual_seconds: int = Field(ge=0)
    qa_seconds: int = Field(default=0, ge=0)


class ReportScoreCardValues(StrictModel):
    engagement: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    credibility: int = Field(ge=0, le=100)


class ReportScoreCardDescriptions(StrictModel):
    engagement: str
    clarity: str
    credibility: str


class ReportScoreCard(StrictModel):
    scores: ReportScoreCardValues
    descriptions: ReportScoreCardDescriptions
    # Compatibility-only input for older V2 fixtures. User averages are mutable
    # account data and therefore do not belong in immutable session feedback.
    average_scores: ReportScoreCardValues | None = Field(default=None, exclude=True)


class HighlightMetric(StrictModel):
    name: str
    score: int = Field(ge=0, le=100)


class DetailAnalysis(StrictModel):
    # These three V1-shaped fields remain accepted for stored-data recovery but
    # are excluded from newly serialized V2 feedback. The canonical V2 detail
    # contract is exactly five content metrics plus five delivery metrics.
    highlight_metrics: list[HighlightMetric] = Field(default_factory=list, exclude=True)
    content_analysis: dict[str, int] = Field(default_factory=dict, exclude=True)
    delivery_analysis: dict[str, int] = Field(default_factory=dict, exclude=True)
    content_metrics: list["DetailMetricFeedback"] = Field(default_factory=list)
    delivery_metrics: list["DetailMetricFeedback"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_canonical_metric_sets(self) -> "DetailAnalysis":
        expected_content = [item.id for item in CONTENT_METRIC_SPECS]
        expected_delivery = [item.id for item in DELIVERY_METRIC_SPECS]
        if [item.id for item in self.content_metrics] != expected_content:
            raise ValueError("content_metrics must contain the canonical five metrics in order")
        if [item.id for item in self.delivery_metrics] != expected_delivery:
            raise ValueError("delivery_metrics must contain the canonical five metrics in order")
        return self


class DetailMetricFeedback(StrictModel):
    id: str
    score: int | None = Field(default=None, ge=0, le=100)
    reason: str = Field(validation_alias=AliasChoices("reason", "summary"))
    evidence_ids: list[str] = Field(default_factory=list)
    coaching: str | None = None
    # Accepted only while reading old fixtures; labels and badges are derived
    # from the stable metric id and score by the client.
    label: str | None = Field(default=None, exclude=True)
    rank_label: str | None = Field(default=None, exclude=True)
    status: Literal["available", "unavailable"] | None = Field(default=None, exclude=True)


class TimelineItem(StrictModel):
    time_sec: int = Field(ge=0)
    title: str
    description: str
    type: Literal["positive", "warning", "negative"]
    slide: int | None = Field(default=None, ge=1)
    source_step: int = Field(ge=1)
    end_sec: int | None = Field(default=None, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    reaction_ids: list[str] = Field(default_factory=list)
    metric_impacts: dict[Literal["engagement", "clarity", "credibility"], float] = Field(
        default_factory=dict
    )


class AudienceGraphPoint(StrictModel):
    time_sec: int = Field(ge=0)
    E: float = Field(ge=-1.0, le=1.0)
    V: float = Field(ge=-1.0, le=1.0)
    C: float = Field(ge=-1.0, le=1.0)


class AudienceEvent(StrictModel):
    time_sec: int = Field(ge=0)
    label: str
    type: Literal["positive", "warning", "negative"]
    source_step: int = Field(ge=1)


class AudienceAnalysis(StrictModel):
    graph: list[AudienceGraphPoint] = Field(default_factory=list)
    events: list[AudienceEvent] = Field(default_factory=list)


class AIInsightItem(StrictModel):
    title: str
    description: str
    action: str
    metric: Literal["engagement", "clarity", "credibility"] | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class AIInsight(StrictModel):
    title: str
    description: str
    strengths: list[AIInsightItem] = Field(default_factory=list)
    improvements: list[AIInsightItem] = Field(default_factory=list)


class DetailMetricNarrative(StrictModel):
    id: str
    reason: str
    coaching: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class ReportNarrativeOutput(StrictModel):
    ai_insight: AIInsight
    metric_narratives: list[DetailMetricNarrative] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def validate_metric_narratives(self) -> "ReportNarrativeOutput":
        expected = [item.id for item in (*CONTENT_METRIC_SPECS, *DELIVERY_METRIC_SPECS)]
        if [item.id for item in self.metric_narratives] != expected:
            raise ValueError("metric_narratives must contain all ten canonical metric ids in order")
        return self


class QuestionAnswerEvidence(StrictModel):
    question_index: int = Field(ge=0)
    question: str
    intent: str | None = None
    answer: str
    answer_duration_sec: float | None = Field(default=None, ge=0.0)


class QuestionScoreValues(StrictModel):
    understanding: int | None = Field(default=None, ge=0, le=100)
    clarity: int | None = Field(default=None, ge=0, le=100)
    evidence: int | None = Field(default=None, ge=0, le=100)


class QuestionFeedback(StrictModel):
    question_index: int = Field(ge=0)
    question: str
    intent: str | None = None
    time_sec: float | None = Field(default=None, ge=0.0)
    answer: str
    answer_duration_sec: float | None = Field(default=None, ge=0.0)
    scores: QuestionScoreValues | None = None
    strength: str | None = None
    improvement: str | None = None
    suggested_answer: str | None = None


class QASessionFeedback(StrictModel):
    score: int | None = Field(default=None, ge=0, le=100)
    summary: str | None = None
    average_answer_seconds: float | None = Field(default=None, ge=0.0)
    questions: list[QuestionFeedback] = Field(default_factory=list)


class TrainingRecommendation(StrictModel):
    id: str
    title: str
    description: str
    duration_minutes: int = Field(default=3, ge=1, le=60)
    type: str = "VR 훈련"
    priority: bool = False
    evidence_ids: list[str] = Field(default_factory=list)


class ReportFeedback(StrictModel):
    # V2 is a standalone contract. V1 compatibility belongs to the web adapter
    # and the isolated legacy_report_v1 package, not to newly persisted V2 JSON.
    version: Literal["presentation-report-v2"] = "presentation-report-v2"
    generation: ReportGenerationMetadata
    score: ReportScore
    duration: ReportDuration
    score_card: ReportScoreCard
    detail_analysis: DetailAnalysis
    timeline: list[TimelineItem] = Field(default_factory=list)
    audience_analysis: AudienceAnalysis
    ai_insight: AIInsight
    # Compatibility input for early V2 payloads. The same question/answer text
    # is already carried by qa_feedback.questions, so canonical V2 output does
    # not persist it twice.
    qa_history: list[QuestionAnswerEvidence] = Field(default_factory=list, exclude=True)
    qa_feedback: QASessionFeedback | None = None
    recommended_trainings: list[TrainingRecommendation] = Field(default_factory=list)
    evidence: list[ReportEvidence] = Field(default_factory=list)
    reaction_trace: list[ReportReactionTrace] = Field(default_factory=list)


class ReportFinishRequest(StrictModel):
    request_id: UUID
    planned_seconds: int = Field(default=0, ge=0, le=86400)
    qa_seconds: int = Field(default=0, ge=0, le=86400)


class ReportFinishResponse(StrictModel):
    session_id: UUID
    status: Literal["ready"] = "ready"
    generated_at: datetime
    persistent_session_id: str | None = None
    report: ReportFeedback


class ReportStatusResponse(StrictModel):
    session_id: UUID
    status: Literal["not_started", "generating", "ready", "failed"]
    persistent_session_id: str | None = None
    error: str | None = None
    report: ReportFeedback | None = None


class ReportRecoveryRequest(StrictModel):
    request_id: UUID
    planned_seconds: int = Field(default=0, ge=0, le=86400)
    qa_seconds: int = Field(default=0, ge=0, le=86400)
