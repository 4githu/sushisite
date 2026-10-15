import json

from .base import ResearchEngine


class FakeEngine(ResearchEngine):
    """Contract exerciser: never assigns substantive scores or claims model inference."""

    def _infer(self, messages):
        rubric = json.loads(messages[1]["content"])["rubric"]
        return {"criteria": [{"criterion_id": criterion["criterion_id"], "score": None,
            "reason": "Fake engine: no model inference or substantive scoring performed.",
            "evidence_ids": [], "abstained": True, "abstain_reason": "fake_engine_not_a_scoring_model"}
            for criterion in rubric["criteria"]]}
