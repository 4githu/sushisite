"""Research16 transport contracts. Criterion definitions always come from a bundle."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Score = Annotated[int, Field(strict=True, ge=1, le=5)]
Count = Annotated[int, Field(strict=True, ge=0)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Anchor(Contract):
    score: Score
    description: Text


class Criterion(Contract):
    criterion_id: Text
    label: Text
    definition: Text
    anchors: tuple[Anchor, ...] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def complete_scale(self):
        if {a.score for a in self.anchors} != {1, 2, 3, 4, 5}:
            raise ValueError("each criterion needs exactly the five supplied 1–5 anchors")
        return self


class RubricBundle(Contract):
    schema_version: Literal["rubric-bundle.v1"] = "rubric-bundle.v1"
    rubric_version: Text
    policy_version: Text
    purpose: Literal["research", "TEST_ONLY"]
    source: Text
    policy: dict[str, JsonValue] = Field(min_length=1)
    criteria: tuple[Criterion, ...] = Field(min_length=16, max_length=16)

    @model_validator(mode="after")
    def unique_criteria(self):
        if len({c.criterion_id for c in self.criteria}) != 16:
            raise ValueError("bundle needs exactly sixteen unique supplied criterion IDs")
        return self


class EvidenceItem(Contract):
    evidence_id: Text
    source_id: Text
    kind: Literal["transcript", "metrics", "slide", "context", "qa"]
    client_time_s: float | None = Field(default=None, ge=0)
    payload: dict[str, JsonValue]
    truncated: bool | None = False


class EvidenceCoverage(Contract):
    available_sources: Count
    total_sources: Count
    omitted_source_ids: tuple[Text, ...] = ()
    truncated: bool = False
    truncation_unknown: bool = False

    @model_validator(mode="after")
    def valid_sources(self):
        if self.total_sources != self.available_sources + len(self.omitted_source_ids):
            raise ValueError("source coverage must include explicitly omitted sources")
        return self


class EvidencePack(Contract):
    schema_version: Literal["evidence-pack.v1"] = "evidence-pack.v1"
    source_id: Text
    source_version: Text
    time_basis: Literal["declared_client_presentation_seconds"] = "declared_client_presentation_seconds"
    items: tuple[EvidenceItem, ...] = Field(min_length=1)
    missing_inputs: tuple[Text, ...]
    coverage: EvidenceCoverage
    excluded_inputs: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def unique_evidence(self):
        ids = [item.evidence_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence ID")
        sources = {item.source_id for item in self.items}
        if len(sources) != self.coverage.available_sources:
            raise ValueError("available source coverage does not match evidence")
        if sources & set(self.coverage.omitted_source_ids):
            raise ValueError("an omitted source cannot also be available")
        return self


class CriterionAssessment(Contract):
    criterion_id: Text
    score: Score | None
    reason: Text
    evidence_ids: tuple[Text, ...] = ()
    abstained: bool = Field(strict=True)
    abstain_reason: Text | None = None

    @model_validator(mode="after")
    def consistent_abstention(self):
        if self.abstained:
            if self.score is not None or self.abstain_reason is None:
                raise ValueError("abstention requires null score and a reason")
        elif self.score is None or self.abstain_reason is not None or not self.evidence_ids:
            raise ValueError("scoring requires 1–5, evidence IDs and no abstain_reason")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("duplicate evidence reference")
        return self


class AssessmentOutput(Contract):
    criteria: tuple[CriterionAssessment, ...] = Field(min_length=16, max_length=16)

    @model_validator(mode="after")
    def unique_results(self):
        if len({c.criterion_id for c in self.criteria}) != 16:
            raise ValueError("result needs sixteen unique criterion IDs")
        return self


class EngineIdentity(Contract):
    provider: Text
    runtime_binding: Literal["builtin_fake", "injected_loader", "transformers_local"]
    model: Text
    model_revision: Text
    tokenizer: Text
    tokenizer_revision: Text
    adapter: Text | None = None
    adapter_revision: Text | None = None
    runtime_versions: dict[str, str]


class InferenceMetadata(Contract):
    call_count: Count
    cache_enabled: bool
    cache_hit: bool
    elapsed_s: float = Field(ge=0)
    settings: dict[str, JsonValue]


class AssessmentCoverage(Contract):
    scored_criteria: Count
    abstained_criteria: Count
    evidence: EvidenceCoverage
    missing_inputs: tuple[Text, ...]


class AssessmentResult(AssessmentOutput):
    schema_version: Literal["research-assessment.v1"] = "research-assessment.v1"
    rubric_version: Text
    policy_version: Text
    rubric_digest: Text
    policy_digest: Text
    rubric_purpose: Literal["research", "TEST_ONLY"]
    prompt_version: Text
    evidence_schema_version: Text
    evidence_source_version: Text
    evidence_digest: Text
    identity: EngineIdentity
    coverage: AssessmentCoverage
    inference: InferenceMetadata
