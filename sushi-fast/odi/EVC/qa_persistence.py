"""Internal, owner-bound Q&A source snapshots. No audio or session tokens stored."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

from odi.db import odidb
from .config import EVC_TRANSCRIPT_RETENTION_DAYS
from .schema import GeneratedQuestion


def persist_qa_state(record, *, questions=None, answers=None, generated_at=None, audience_bindings=None):
    if not record.pre_session_pin:
        return
    if not record.owner_user_id:
        raise PermissionError("linked Q&A is missing ownership metadata")
    date = generated_at or record.question_generated_at
    state = {"schema_version": "qa-source.v1",
        "questions": [q.model_dump(mode="json") for q in (questions if questions is not None else record.generated_questions)],
        "answers": {str(k): deepcopy(v) for k, v in (answers if answers is not None else record.qa_answers).items()},
        "audience_bindings": {str(k): v for k, v in (audience_bindings if audience_bindings is not None else record.qa_audience_bindings).items()},
        "generated_at": date.isoformat() if date else None,
        "generation_request_id": str(record.question_generation_request_id) if record.question_generation_request_id else None}
    expires_at = (datetime.now(timezone.utc) + timedelta(days=EVC_TRANSCRIPT_RETENTION_DAYS)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    odidb.save_presentation_qa(evc_session_id=str(record.session_id), owner_user_id=record.owner_user_id,
        pre_session_pin=record.pre_session_pin, state=state, expires_at=expires_at)


def bind_question_audience(record, index, audience_id):
    bindings = {**record.qa_audience_bindings, index: audience_id}
    persist_qa_state(record, audience_bindings=bindings)
    record.qa_audience_bindings = bindings


def restore_qa_state(record):
    if not record.pre_session_pin or not record.owner_user_id:
        raise PermissionError("linked Q&A is missing ownership metadata")
    state = odidb.get_presentation_qa(str(record.session_id), owner_user_id=record.owner_user_id,
                                    pre_session_pin=record.pre_session_pin)
    if state is None:
        return False
    if state.get("schema_version") != "qa-source.v1":
        raise ValueError("unsupported Q&A source version")
    record.generated_questions = [GeneratedQuestion.model_validate(q) for q in state["questions"]]
    record.qa_answers = {int(k): v for k, v in state["answers"].items()}
    record.qa_audience_bindings = {int(k): v for k, v in state.get("audience_bindings", {}).items()}
    record.question_generation_request_id = UUID(state["generation_request_id"]) if state.get("generation_request_id") else None
    record.question_generated_at = datetime.fromisoformat(state["generated_at"]) if state.get("generated_at") else None
    record.question_generation_status = "ready"
    record.question_response_cache.clear()
    return True
