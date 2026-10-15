from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from .config import EVC_MIN_TRANSCRIPT_CHARS
from .question_generation import QuestionGenerationProvider, generate_questions
from .schema import QuestionGenerationResponse, QuestionListResponse
from .session_store import SessionStore, session_store


class QuestionGenerationError(RuntimeError):
    pass


class TranscriptTooShortError(QuestionGenerationError):
    pass


class QuestionGenerationInProgressError(QuestionGenerationError):
    pass


class QuestionsNotGeneratedError(QuestionGenerationError):
    pass


async def generate_session_questions(
    *,
    session_id: UUID,
    token: str,
    request_id: UUID,
    question_count: int,
    provider: QuestionGenerationProvider | None = None,
    store: SessionStore = session_store,
    min_transcript_chars: int = EVC_MIN_TRANSCRIPT_CHARS,
) -> QuestionGenerationResponse:
    async with store.locked_session(session_id, token) as record:
        cached = record.question_response_cache.get(request_id)
        if cached is not None:
            return cached
        if record.question_generation_status == "ready":
            response = _response_for(record)
            _cache_response(record, request_id, response)
            return response
        if record.question_generation_status == "generating":
            raise QuestionGenerationInProgressError("questions are already being generated")

        transcript = "\n".join(item.text for item in record.transcript_segments).strip()
        if len(transcript) < min_transcript_chars:
            raise TranscriptTooShortError(
                f"presentation transcript must contain at least {min_transcript_chars} characters"
            )
        record.presentation_status = "finishing"
        record.question_generation_status = "generating"
        record.question_generation_request_id = request_id
        record.question_generation_error = None
        payload = {
            "presentation_title": record.presentation_title,
            "slides_outline": [
                {"index": item.index, "title": item.title, "summary": item.summary}
                for item in record.slides
            ],
            "transcript_segments": [item.model_dump() for item in record.transcript_segments],
            "recent_segment_notes": record.segment_notes[-8:],
            "audience_profiles": [
                {"agent_id": item.agent_id, "profile": item.profile.model_dump()}
                for item in record.audiences
            ],
            "question_count": question_count,
            "language": "ko-KR",
        }

    try:
        generated = await generate_questions(payload, provider=provider)
    except Exception as exc:
        async with store.locked_session(session_id, token) as record:
            record.presentation_status = "finished"
            record.question_generation_status = "failed"
            record.question_generation_error = type(exc).__name__
        raise

    async with store.locked_session(session_id, token) as record:
        generated_at = datetime.now(timezone.utc)
        record.generated_questions = generated.questions
        record.question_generated_at = generated_at
        record.presentation_status = "finished"
        record.question_generation_status = "ready"
        record.question_generation_error = None
        response = QuestionGenerationResponse(
            session_id=record.session_id,
            generated_at=generated_at,
            questions=record.generated_questions,
        )
        _cache_response(record, request_id, response)
        return response


async def list_session_questions(
    *,
    session_id: UUID,
    token: str,
    store: SessionStore = session_store,
) -> QuestionListResponse:
    async with store.locked_session(session_id, token) as record:
        if record.question_generation_status == "generating":
            raise QuestionGenerationInProgressError("questions are being generated")
        if record.question_generation_status != "ready":
            raise QuestionsNotGeneratedError("questions have not been generated")
        return QuestionListResponse(
            session_id=record.session_id,
            total=len(record.generated_questions),
            questions=record.generated_questions,
        )


def _response_for(record) -> QuestionGenerationResponse:
    assert record.question_generated_at is not None
    return QuestionGenerationResponse(
        session_id=record.session_id,
        generated_at=record.question_generated_at,
        questions=record.generated_questions,
    )


def _cache_response(record, request_id: UUID, response: QuestionGenerationResponse) -> None:
    record.question_response_cache[request_id] = response
    record.question_response_cache.move_to_end(request_id)
    while len(record.question_response_cache) > 32:
        record.question_response_cache.popitem(last=False)
