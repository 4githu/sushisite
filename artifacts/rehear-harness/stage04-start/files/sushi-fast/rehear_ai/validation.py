"""Structural integrity, not proof that a cited fact semantically supports a score."""
import hashlib
import json

from .contracts import AssessmentResult, EvidencePack, RubricBundle


def digest(value) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_assessment(result: AssessmentResult, evidence: EvidencePack, rubric: RubricBundle) -> AssessmentResult:
    # Revalidate even objects made with Pydantic model_copy/update or model_construct.
    result = AssessmentResult.model_validate(result.model_dump(mode="json"))
    evidence = EvidencePack.model_validate(evidence.model_dump(mode="json"))
    rubric = RubricBundle.model_validate(rubric.model_dump(mode="json"))
    if {c.criterion_id for c in result.criteria} != {c.criterion_id for c in rubric.criteria}:
        raise ValueError("result IDs must exactly match the supplied sixteen rubric IDs")
    ids = {item.evidence_id for item in evidence.items}
    if any(not set(c.evidence_ids) <= ids for c in result.criteria):
        raise ValueError("result references unknown evidence IDs")
    if (result.rubric_version, result.policy_version, result.rubric_purpose) != (rubric.rubric_version, rubric.policy_version, rubric.purpose):
        raise ValueError("result rubric/policy provenance mismatch")
    if result.rubric_digest != digest(rubric) or result.policy_digest != digest(rubric.policy):
        raise ValueError("result rubric/policy content mismatch")
    if result.evidence_digest != digest(evidence) or result.evidence_source_version != evidence.source_version or result.evidence_schema_version != evidence.schema_version:
        raise ValueError("result evidence provenance mismatch")
    scored = sum(c.score is not None for c in result.criteria)
    if result.coverage.scored_criteria != scored or result.coverage.abstained_criteria != 16 - scored:
        raise ValueError("incorrect criterion coverage")
    if result.coverage.evidence != evidence.coverage or result.coverage.missing_inputs != evidence.missing_inputs:
        raise ValueError("incorrect evidence coverage")
    return result
