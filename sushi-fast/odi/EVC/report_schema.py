from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from .schema import AudienceState, MtDtEvaluation, SpeechMetrics, StrictModel


class ReportSegmentRecord(StrictModel):
    step: int = Field(ge=1)
    client_time_s: float = Field(ge=0.0)
    slide_index: int = Field(ge=0)
    transcript: str = Field(min_length=1)
    evaluation: MtDtEvaluation
    speech_metrics: SpeechMetrics
    evc_state: AudienceState
    warnings: list[str] = Field(default_factory=list)


class ReportGenerationMetadata(StrictModel):
    generated_at: datetime
    generator: str
    source_segment_count: int = Field(ge=0)
    transcript_word_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class ReportScore(StrictModel):
    overall_score: int = Field(ge=0, le=100)
    percentile: int | None = Field(default=None, ge=0, le=100)
    grade: str


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


class HighlightMetric(StrictModel):
    name: str
    score: int = Field(ge=0, le=100)


class DetailAnalysis(StrictModel):
    highlight_metrics: list[HighlightMetric] = Field(default_factory=list)
    content_analysis: dict[str, int]
    delivery_analysis: dict[str, int]


class TimelineItem(StrictModel):
    time_sec: int = Field(ge=0)
    title: str
    description: str
    type: Literal["positive", "warning", "negative"]
    slide: int | None = Field(default=None, ge=1)
    source_step: int = Field(ge=1)


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


class AIInsight(StrictModel):
    title: str
    description: str


class ReportFeedback(StrictModel):
    version: Literal["presentation-report-v1"] = "presentation-report-v1"
    generation: ReportGenerationMetadata
    score: ReportScore
    duration: ReportDuration
    score_card: ReportScoreCard
    detail_analysis: DetailAnalysis
    timeline: list[TimelineItem] = Field(default_factory=list)
    audience_analysis: AudienceAnalysis
    ai_insight: AIInsight


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
