from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class ProductMode(str, Enum):
    EDUCATION = "education"
    PRESENTATION = "presentation"


class AnalysisStatus(str, Enum):
    COMPLETED = "COMPLETED"
    UNDETERMINED = "UNDETERMINED"
    ERROR = "ERROR"


class AlignmentStatus(str, Enum):
    CORRECT = "CORRECT"
    SUBSTITUTION = "SUBSTITUTION"
    DELETION = "DELETION"
    INSERTION = "INSERTION"
    UNDETERMINED = "UNDETERMINED"


class SpeechWord(BaseModel):
    word: str
    start: float
    end: float
    confidence: float = 0.0


class SpeechTextResult(BaseModel):
    transcript: str
    words: list[SpeechWord] = Field(default_factory=list)


class SentenceIssue(BaseModel):
    target_text: str
    recognized_text: str | None = None

    target_start_index: int | None = None
    target_end_index: int | None = None

    target_word: str | None = None
    target_syllable: str | None = None

    issue_type: Literal[
        "substitution",
        "omission",
        "insertion",
        "unclear",
        "timing",
        "unknown",
    ]

    severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)

    comment: str
    practice_instruction: str


class SentenceAnalysis(BaseModel):
    pronunciation_score: float = Field(ge=0.0, le=100.0)
    needs_repractice: bool
    summary_comment: str
    issues: list[SentenceIssue] = Field(default_factory=list)


class SentencePronunciationResult(BaseModel):
    target_text: str
    transcript: str
    text_accuracy: float = Field(ge=0.0, le=100.0)
    pronunciation_score: float = Field(ge=0.0, le=100.0)
    needs_repractice: bool
    summary_comment: str
    words: list[SpeechWord] = Field(default_factory=list)
    issues: list[SentenceIssue] = Field(default_factory=list)


class LPCPoint(ApiModel):
    frequency_hz: float
    magnitude_db: float


class FormantPoint(ApiModel):
    name: Literal["F1", "F2", "F3"]
    frequency_hz: float
    magnitude_db: float | None = None


class LPCAnalysis(ApiModel):
    sample_rate: int
    duration_seconds: float
    lpc_order: int
    valid_signal: bool
    comment: str
    points: list[LPCPoint] = Field(default_factory=list)
    formants: list[FormantPoint] = Field(default_factory=list)


class SyllableComparisonResult(BaseModel):
    target_syllable: str
    similarity_score: float = Field(ge=0.0, le=100.0)
    user: LPCAnalysis
    reference: LPCAnalysis
    comment: str


class SttMetadata(ApiModel):
    provider: str
    model: str
    verification_used: bool = False
    verification_agreement: bool | None = None
    verification_provider: str | None = None
    verification_model: str | None = None


class TranscriptInfo(ApiModel):
    raw_transcript: str
    display_transcript: str
    target_text: str | None = None
    generated_from_audio: bool = False
    text_accuracy_applicable: bool = True


class AlignmentEvidence(ApiModel):
    evidence_type: str
    description: str
    limitation: str


class WordTiming(ApiModel):
    transcript_index: int
    text: str
    start_sec: float
    end_sec: float
    stt_confidence: float = Field(ge=0.0, le=1.0)


class SyllableResult(ApiModel):
    target_index: int | None = None
    transcript_index: int | None = None
    expected: str | None = None
    recognized: str | None = None
    status: AlignmentStatus


class ErrorLocation(ApiModel):
    target_start_char_index: int | None = None
    target_end_char_index_exclusive: int | None = None
    display_char_position: int | None = None
    target_word_index: int | None = None
    target_syllable_index: int | None = None
    display_label: str | None = None
    position_basis: str = "ORIGINAL_TEXT_1_BASED_FOR_DISPLAY"


class Observation(ApiModel):
    expected: str | None = None
    recognized: str | None = None
    status: AlignmentStatus
    message: str


class PracticeGuidance(ApiModel):
    tip_type: str = "ARTICULATION_REFERENCE"
    tip: str | None = None
    articulation_tip_id: str | None = None
    practice_resource_id: str | None = None


class WordResult(ApiModel):
    target_index: int | None = None
    transcript_index: int | None = None
    expected: str | None = None
    recognized: str | None = None
    status: AlignmentStatus
    target_start_char_index: int | None = None
    target_end_char_index_exclusive: int | None = None
    evidence_source: str
    recognized_word_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    syllable_results: list[SyllableResult] = Field(default_factory=list)
    location: ErrorLocation | None = None
    observation: Observation | None = None
    practice: PracticeGuidance | None = None


class AudioMetrics(ApiModel):
    duration_sec: float
    speech_duration_sec: float
    silence_duration_sec: float
    silence_ratio: float = Field(ge=0.0, le=1.0)
    long_pause_count: int = Field(ge=0)
    average_rms: float
    peak_rms: float
    speaking_rate_cpm: float | None = None
    filler_count: int = Field(ge=0)


class EvaluationScore(ApiModel):
    overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    text_match_score: float | None = Field(default=None, ge=0.0, le=100.0)
    timing_score: float | None = Field(default=None, ge=0.0, le=100.0)
    pause_score: float | None = Field(default=None, ge=0.0, le=100.0)
    fluency_score: float | None = Field(default=None, ge=0.0, le=100.0)
    delivery_score: float | None = Field(default=None, ge=0.0, le=100.0)
    score_basis: str
    matched_syllable_count: int = Field(ge=0)
    total_target_syllable_count: int = Field(ge=0)


class PracticeItem(ApiModel):
    expected: str
    recognized: str | None = None
    practice_resource_id: str | None = None
    articulation_tip_id: str | None = None
    tip: str | None = None


class Feedback(ApiModel):
    status: Literal["AVAILABLE", "UNAVAILABLE"]
    summary: str | None = None
    practice_items: list[PracticeItem] = Field(default_factory=list)
    next_action: str | None = None


class LpcSyllableSegment(ApiModel):
    transcript_index: int
    word: str
    syllable_index: int
    syllable: str
    word_start_sec: float
    word_end_sec: float
    segment_start_sec: float
    segment_end_sec: float
    analysis_start_sec: float
    analysis_end_sec: float
    window_strategy: str
    analysis: LPCAnalysis


class LpcResult(ApiModel):
    enabled: bool
    segmentation_method: str
    vowel_window_method: str
    segments: list[LpcSyllableSegment] = Field(default_factory=list)


class VoiceEvaluationResponse(ApiModel):
    api_version: str = "v1"
    request_id: str
    session_id: str
    attempt_id: str
    mode: ProductMode
    analysis_status: AnalysisStatus
    requires_retry: bool
    retry_reason: str | None = None
    needs_repractice: bool
    target_text: str | None = None
    transcript: str
    transcript_info: TranscriptInfo | None = None
    confidence_note: str
    stt: SttMetadata
    alignment_evidence: AlignmentEvidence | None = None
    score: EvaluationScore
    words: list[WordTiming] = Field(default_factory=list)
    word_results: list[WordResult] = Field(default_factory=list)
    metrics: AudioMetrics | None = None
    feedback: Feedback
