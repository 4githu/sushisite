"""Answer-driven Q&A, using the existing question provider and session authentication."""
from __future__ import annotations

import hashlib
import io
import wave
from uuid import UUID

from fastapi import HTTPException

from .question_generation import generate_questions, QuestionGenerationProviderError
from .session_store import session_store


def checked_question(record, index):
    if record.question_generation_status != "ready" or not 0 <= index < len(record.generated_questions):
        raise HTTPException(404, "Question not found")
    return record.generated_questions[index]


async def submit_answer(*, session_id, token, index, request_id: UUID, audio: bytes,
                        next_audience_id="", provider=None, transcriber=None, store=session_store):
    from .azure_speech import validate_wav
    from .speech2text import transcribe_wav_bytes
    # Authenticate before accepting work; serialize only this session's Q&A requests.
    record = await store.get_authorized_session(session_id, token)
    digest = hashlib.sha256(audio).hexdigest()
    validate_wav(audio)
    with wave.open(io.BytesIO(audio), "rb") as stream:
        answer_duration_s = round(stream.getnframes() / stream.getframerate(), 3)
    async with record.qa_lock:
        async with store.locked_session(session_id, token) as record:
            question = checked_question(record, index)
            entry = record.qa_answers.get(index)
            if any(v["request_id"] == str(request_id) for k, v in record.qa_answers.items() if k != index):
                raise HTTPException(409, "Request id already used")
            if entry and (entry["request_id"] != str(request_id) or entry["audio_hash"] != digest or
                          entry["next_audience_id"] != next_audience_id):
                raise HTTPException(409, "Answer already submitted with different data")
            if entry and entry.get("response"):
                return entry["response"]
            if record.report_generation_status in ("generating", "ready"):
                raise HTTPException(409, "Session is already finishing")
            if index != sum(bool(v.get("response")) for v in record.qa_answers.values()):
                raise HTTPException(409, "Answer the current question first")
            next_actor = next((a for a in record.audiences if a.agent_id == next_audience_id), None)
            if index + 1 < len(record.generated_questions) and next_actor is None:
                raise HTTPException(422, "Next question audience is required")
            if entry is None:
                entry = {"request_id": str(request_id), "audio_hash": digest,
                         "question_index": index, "question": question.question,
                         "intent": question.intent,
                         "next_audience_id": next_audience_id, "transcript": "",
                         "answer_duration_s": answer_duration_s}
                record.qa_answers[index] = entry

        if not entry["transcript"]:
            if transcriber is not None:
                transcript = (await transcriber(audio)).strip()
            else:
                result = await transcribe_wav_bytes(
                    audio,
                    provider_name=record.stt_provider_name,
                )
                transcript = result.transcript.strip()
            if not transcript:
                async with store.locked_session(session_id, token) as record:
                    del record.qa_answers[index]
                return {"question_index": index, "request_id": str(request_id),
                        "saved": False, "transcript": "", "next_question": None}
            # Keep recognized text even if the LLM fails. Retrying must not re-transcribe.
            async with store.locked_session(session_id, token) as record:
                entry["transcript"] = transcript

        async with store.locked_session(session_id, token) as record:
            total = len(record.generated_questions)
            history = [{"question_index": k, "question": v["question"], "answer": v["transcript"]}
                       for k, v in sorted(record.qa_answers.items()) if v["transcript"]]
            payload = {
                "presentation_title": record.presentation_title,
                "slides_outline": [{"index": s.index, "title": s.title, "summary": s.summary} for s in record.slides],
                "transcript_segments": [s.model_dump() for s in record.transcript_segments],
                "recent_segment_notes": record.segment_notes[-8:],
                "qa_history": history, "question_count": 1, "language": "ko-KR",
                "next_question_order": index + 2, "total_question_count": total,
                "next_audience": next_actor.model_dump() if next_actor else None,
                "mode": "adaptive_next_question",
            }
        next_question = None
        if index + 1 < total:
            generated = await generate_questions(payload, provider=provider)
            candidate = generated.questions[0]
            if " ".join(candidate.question.lower().split()) in {
                " ".join(h["question"].lower().split()) for h in history
            }:
                raise QuestionGenerationProviderError("Next question repeats an answered question")
            next_question = candidate.model_copy(update={"id": f"q{index + 2}", "order": index + 2})

        async with store.locked_session(session_id, token) as record:
            if next_question:
                record.generated_questions[index + 1] = next_question
                # Initial generation cache must not return the superseded question list.
                record.question_response_cache.clear()
            response = {"question_index": index, "request_id": str(request_id), "saved": True,
                        "transcript": entry["transcript"], "total": total,
                        "next_question": next_question.model_dump() if next_question else None}
            entry["response"] = response
            return response
