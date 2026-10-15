"""Build evidence from a neutral export; do not infer unavailable timestamps/features."""
from pydantic import Field, StrictFloat, StrictInt, field_validator, model_validator

from .contracts import Contract, EvidenceCoverage, EvidenceItem, EvidencePack, Text

OBSERVED_METRICS = ("duration_s", "word_count", "speech_rate_wps", "pause_count", "pause_total_s",
                    "filler_count", "repeated_word_count", "avg_confidence")


class Word(Contract):
    word: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self):
        if self.end < self.start:
            raise ValueError("word end precedes start")
        return self


class SourceSegment(Contract):
    source_id: Text
    step: int = Field(strict=True, ge=1)
    client_time_s: float = Field(ge=0)
    segment_offset_s: float | None = Field(default=None, ge=0)
    transcript: str = Field(min_length=1)
    words: tuple[Word, ...] | None = None
    speech_metrics: dict[str, StrictFloat | StrictInt] = Field(default_factory=dict)
    gaze_scalar: float | None = Field(default=None, ge=-1, le=1)
    slide_index: int | None = Field(default=None, strict=True, ge=0)
    slide_text: str | None = None
    slide_text_truncated: bool | None = None
    transcript_truncated: bool = False
    missing_inputs: tuple[Text, ...] = ()

    @field_validator("speech_metrics")
    @classmethod
    def observed_metrics_only(cls, value):
        if not value.keys() <= set(OBSERVED_METRICS):
            raise ValueError("neutral metrics must be measured preprocessor outputs, not model/report scores")
        return value


class QAObservation(Contract):
    source_id: Text
    question: str
    answer: str | None


class SourceCase(Contract):
    source_id: Text
    segments: tuple[SourceSegment, ...] = Field(min_length=1)
    qa_history: tuple[QAObservation, ...] | None = None
    omitted_source_ids: tuple[Text, ...] = ()
    truncated: bool = False
    excluded_inputs: tuple[Text, ...] = ()


def build_evidence_pack(records: dict, *, source_version: str) -> EvidencePack:
    case = SourceCase.model_validate(records)
    source_ids = [segment.source_id for segment in case.segments]
    source_ids += [entry.source_id for entry in case.qa_history or ()]
    if len(source_ids) != len(set(source_ids)) or len({s.step for s in case.segments}) != len(case.segments):
        raise ValueError("duplicate source ID or segment step")
    if len(set(case.omitted_source_ids)) != len(case.omitted_source_ids):
        raise ValueError("duplicate omitted source ID")
    items, missing = [], ["f0", "volume", "gaze_time_series", "slide_timeline", "external_fact_sources"]
    for segment in case.segments:
        missing.extend(segment.missing_inputs)
        words = None
        if segment.words is None:
            missing.append("word_timestamps")
        else:
            words = [{**word.model_dump(),
                "presentation_start_s": segment.segment_offset_s + word.start if segment.segment_offset_s is not None else None,
                "presentation_end_s": segment.segment_offset_s + word.end if segment.segment_offset_s is not None else None}
                for word in segment.words]
        if segment.segment_offset_s is None:
            missing.append("word_presentation_offsets")
        def add(kind, payload, truncated=False):
            items.append(EvidenceItem(evidence_id=f"{segment.source_id}:{kind}", source_id=segment.source_id,
                kind=kind, client_time_s=segment.client_time_s, payload=payload, truncated=truncated))
        add("transcript", {"text": segment.transcript, "step": segment.step,
            "segment_offset_s": segment.segment_offset_s, "word_time_basis": "segment_relative_seconds",
            "words": words}, segment.transcript_truncated)
        if segment.speech_metrics:
            add("metrics", segment.speech_metrics)
        if segment.gaze_scalar is not None:
            add("context", {"gaze_scalar": segment.gaze_scalar, "precision": "scalar_only"})
        else:
            missing.append("gaze_scalar")
        if segment.slide_index is not None:
            add("slide", {"index": segment.slide_index, "text": segment.slide_text,
                "precision": "segment_observation_only"}, segment.slide_text_truncated)
            if segment.slide_text is None:
                missing.append("slide_text")
            if segment.slide_text_truncated is None:
                missing.append("slide_text_completeness")
        else:
            missing.append("slide_context")
    if case.qa_history is None:
        missing.append("qa_history")
    for qa in case.qa_history or ():
        if not qa.answer or not qa.answer.strip():
            missing.append("qa_answer")
        items.append(EvidenceItem(evidence_id=f"{qa.source_id}:qa", source_id=qa.source_id,
            kind="qa", payload={"question": qa.question, "answer": qa.answer}))
    return EvidencePack(source_id=case.source_id, source_version=source_version, items=tuple(items),
        missing_inputs=tuple(dict.fromkeys(missing)), excluded_inputs=case.excluded_inputs,
        coverage=EvidenceCoverage(available_sources=len(source_ids),
            total_sources=len(source_ids) + len(case.omitted_source_ids), omitted_source_ids=case.omitted_source_ids,
            truncated=case.truncated or bool(case.omitted_source_ids) or any(item.truncated is True for item in items),
            truncation_unknown=any(item.truncated is None for item in items)))
