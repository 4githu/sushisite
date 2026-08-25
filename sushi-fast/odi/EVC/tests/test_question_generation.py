import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from odi.EVC.pipeline import create_pipeline_session
from odi.EVC.question_generation import (
    QuestionGenerationProviderError,
    generate_questions,
)
from odi.EVC.question_service import (
    QuestionGenerationInProgressError,
    TranscriptTooShortError,
    generate_session_questions,
    list_session_questions,
)
from odi.EVC.router import router
from odi.EVC.schema import (
    GeneratedQuestion,
    GeneratedQuestionSet,
    SmartStartOptions,
    TranscriptSegment,
)
from odi.EVC.session_store import SessionStore, session_store


def question_set(count: int = 3) -> GeneratedQuestionSet:
    return GeneratedQuestionSet(
        questions=[
            GeneratedQuestion(
                id=f"q{index}",
                order=index,
                question=f"발표 내용에 근거한 질문 {index}은 무엇인가요?",
                intent=f"검증 의도 {index}",
                source_steps=[1],
            )
            for index in range(1, count + 1)
        ]
    )


class Provider:
    def __init__(self, result=None):
        self.result = result or question_set()
        self.calls = 0

    def generate(self, payload):
        self.calls += 1
        assert payload["question_count"] == 3
        assert payload["transcript_segments"][0]["step"] == 1
        return self.result


def test_question_provider_validates_count_duplicates_and_source_steps() -> None:
    async def scenario() -> None:
        payload = {
            "question_count": 3,
            "transcript_segments": [{"step": 1}],
        }
        provider = Provider()
        result = await generate_questions(payload, provider=provider, retries=0)
        assert len(result.questions) == 3

        with pytest.raises(QuestionGenerationProviderError):
            await generate_questions(
                payload,
                provider=Provider(question_set(2)),
                retries=0,
            )

        duplicate = question_set()
        duplicate.questions[1].question = duplicate.questions[0].question
        with pytest.raises(QuestionGenerationProviderError):
            await generate_questions(payload, provider=Provider(duplicate), retries=0)

        invalid_source = question_set()
        invalid_source.questions[0].source_steps = [99]
        with pytest.raises(QuestionGenerationProviderError):
            await generate_questions(payload, provider=Provider(invalid_source), retries=0)

    asyncio.run(scenario())


def test_session_generation_is_idempotent_and_finishes_presentation() -> None:
    async def scenario() -> None:
        store = SessionStore()
        started = await create_pipeline_session(
            SmartStartOptions(presentation_title="질문 생성 테스트", seed=7),
            store=store,
        )
        record = await store.get_authorized_session(started.session_id, started.session_token)
        record.transcript_segments.append(
            TranscriptSegment(
                step=1,
                client_time_s=1.0,
                slide_index=0,
                text="발표 내용이 충분히 길다고 가정하는 테스트 전사입니다.",
                word_count=7,
            )
        )
        provider = Provider()
        request_id = uuid4()
        first = await generate_session_questions(
            session_id=started.session_id,
            token=started.session_token,
            request_id=request_id,
            question_count=3,
            provider=provider,
            store=store,
            min_transcript_chars=10,
        )
        repeated = await generate_session_questions(
            session_id=started.session_id,
            token=started.session_token,
            request_id=request_id,
            question_count=3,
            provider=provider,
            store=store,
            min_transcript_chars=10,
        )
        listed = await list_session_questions(
            session_id=started.session_id,
            token=started.session_token,
            store=store,
        )
        assert repeated == first
        assert listed.questions == first.questions
        assert provider.calls == 1
        assert record.presentation_status == "finished"
        assert record.question_generation_status == "ready"

    asyncio.run(scenario())


def test_short_transcript_and_concurrent_generation_are_rejected() -> None:
    async def scenario() -> None:
        store = SessionStore()
        started = await create_pipeline_session(
            SmartStartOptions(presentation_title="짧은 발표", seed=8),
            store=store,
        )
        with pytest.raises(TranscriptTooShortError):
            await generate_session_questions(
                session_id=started.session_id,
                token=started.session_token,
                request_id=uuid4(),
                question_count=3,
                provider=Provider(),
                store=store,
                min_transcript_chars=10,
            )
        record = await store.get_authorized_session(started.session_id, started.session_token)
        record.question_generation_status = "generating"
        with pytest.raises(QuestionGenerationInProgressError):
            await generate_session_questions(
                session_id=started.session_id,
                token=started.session_token,
                request_id=uuid4(),
                question_count=3,
                provider=Provider(),
                store=store,
                min_transcript_chars=0,
            )

    asyncio.run(scenario())


def test_question_api_generates_then_returns_stable_get(monkeypatch) -> None:
    async def fake_generate(payload, **kwargs):
        return question_set()

    monkeypatch.setattr("odi.EVC.question_service.generate_questions", fake_generate)

    async def scenario() -> None:
        started = await create_pipeline_session(
            SmartStartOptions(presentation_title="API 질문 테스트", seed=9),
            store=session_store,
        )
        record = await session_store.get_authorized_session(
            started.session_id, started.session_token
        )
        record.transcript_segments.append(
            TranscriptSegment(
                step=1,
                client_time_s=1.0,
                slide_index=0,
                text="질문 생성을 위한 충분한 발표 전사입니다. " * 5,
                word_count=30,
            )
        )
        app = FastAPI()
        app.include_router(router, prefix="/odi")
        headers = {"X-EVC-Session-Token": started.session_token}
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            generated = await client.post(
                f"/odi/xreal_rehear/evc/sessions/{started.session_id}/questions/generate",
                headers=headers,
                json={"request_id": str(uuid4()), "question_count": 3},
            )
            assert generated.status_code == 200, generated.text
            fetched = await client.get(
                f"/odi/xreal_rehear/evc/sessions/{started.session_id}/questions",
                headers=headers,
            )
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["questions"] == generated.json()["questions"]
            assert fetched.json()["total"] == 3
        await session_store.delete_session(started.session_id, started.session_token)

    asyncio.run(scenario())
