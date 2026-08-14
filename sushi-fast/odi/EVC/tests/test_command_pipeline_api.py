import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from odi.EVC.clip_pool import load_clip_pool
from odi.EVC.command_builder import build_unity_commands
from odi.EVC.evaluation import EvaluationProviderError
from odi.EVC.pipeline import (
    ClientTimeRegressionError,
    StepConflictError,
    create_pipeline_session,
    update_pipeline,
)
from odi.EVC.router import router
from odi.EVC.schema import (
    AudienceProfile,
    AudienceRuntimeState,
    AudienceState,
    BehaviorChoice,
    ChannelPreference,
    ContentScores,
    DeliveryScores,
    MtDtEvaluation,
    SegmentContext,
    SmartStartOptions,
    SpeechMetrics,
    SpeechTextResult,
    SpeechWord,
)
from odi.EVC.session_store import SessionStore


class STTProvider:
    def transcribe(self, file_path, language):
        return SpeechTextResult(
            transcript="발표 목적을 설명합니다",
            words=[SpeechWord(word="목적", start=0.0, end=0.5, confidence=0.95)],
        )


class EvaluationProvider:
    def evaluate(self, payload):
        from odi.EVC.schema import GPTDeliveryScores, SegmentEvaluation

        return SegmentEvaluation(
            move="Purpose",
            content=ContentScores(
                organization=0.2,
                supporting_material=0.1,
                central_message=0.3,
                cer_validity=0.1,
            ),
            delivery=GPTDeliveryScores(
                language_clarity=0.4,
                slide_speech_alignment=0.0,
            ),
            segment_note="목적 설명",
            short_reason="명확함",
            missing_inputs=[],
            confidence=0.8,
        )


def test_command_builder_decomposes_layers_and_action_priority() -> None:
    target = AudienceRuntimeState(
        agent_id="audience_01",
        profile=AudienceProfile(
            row="front",
            seat="left",
            has_laptop=False,
            responsiveness=0.5,
            expressivity=0.6,
            critical_bias=0.5,
            channel_preference=ChannelPreference(Face=0.3, Body=0.3, GazeHead=0.4),
        ),
        state=AudienceState(E=0.8, V=-0.8, C=0.2),
    )
    commands = build_unity_commands(
        agent=target,
        core=BehaviorChoice(
            behavior_id="EM_05",
            variation_id="EM_05.skeptical_monitoring",
            probability=0.7,
        ),
        action=BehaviorChoice(
            behavior_id="ACT_07",
            variation_id="ACT_07.self_contact",
            probability=1.0,
        ),
        catalog=load_clip_pool(),
        context=SegmentContext(client_time_s=10.0),
        accepted_time_s=10.0,
    )

    assert {command.start_time for command in commands} == {10.1}
    assert {command.priority for command in commands} == {50, 100}
    core_sync = {command.sync_group for command in commands if command.priority == 50}
    action_sync = {command.sync_group for command in commands if command.priority == 100}
    assert len(core_sync) == 1
    assert len(action_sync) == 1
    assert core_sync != action_sync
    assert all(command.intensity == 0.6 for command in commands)


def test_pipeline_update_is_atomic_idempotent_and_step_guarded(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = SessionStore()
        created = await create_pipeline_session(
            SmartStartOptions(presentation_title="테스트", seed=1234),
            store=store,
        )
        context = SegmentContext(
            utterance_position="utterance_boundary",
            client_time_s=10.0,
        )
        request_id = uuid4()
        response = await update_pipeline(
            session_id=created.session_id,
            token=created.session_token,
            request_id=request_id,
            expected_step=0,
            context=context,
            audio_path=tmp_path / "unused.wav",
            stt_provider=STTProvider(),
            evaluation_provider=EvaluationProvider(),
            store=store,
        )
        assert response.step == 1
        assert len(response.audiences) == 6
        assert all(command.agent_id.startswith("audience_0") for command in response.commands)

        repeated = await update_pipeline(
            session_id=created.session_id,
            token=created.session_token,
            request_id=request_id,
            expected_step=0,
            context=context,
            audio_path=tmp_path / "unused.wav",
            stt_provider=STTProvider(),
            evaluation_provider=EvaluationProvider(),
            store=store,
        )
        assert repeated == response
        record = await store.get_authorized_session(created.session_id, created.session_token)
        assert record.step == 1

        with pytest.raises(StepConflictError):
            await update_pipeline(
                session_id=created.session_id,
                token=created.session_token,
                request_id=uuid4(),
                expected_step=0,
                context=context,
                audio_path=tmp_path / "unused.wav",
                stt_provider=STTProvider(),
                evaluation_provider=EvaluationProvider(),
                store=store,
            )

        with pytest.raises(ClientTimeRegressionError):
            await update_pipeline(
                session_id=created.session_id,
                token=created.session_token,
                request_id=uuid4(),
                expected_step=1,
                context=context.model_copy(update={"client_time_s": 9.0}),
                audio_path=tmp_path / "unused.wav",
                stt_provider=STTProvider(),
                evaluation_provider=EvaluationProvider(),
                store=store,
            )

    asyncio.run(scenario())


def test_provider_failure_does_not_commit_state(tmp_path: Path) -> None:
    class FailingEvaluation:
        def evaluate(self, payload):
            raise EvaluationProviderError("failed")

    async def scenario() -> None:
        store = SessionStore()
        created = await create_pipeline_session(
            SmartStartOptions(presentation_title="테스트", seed=1234),
            store=store,
        )
        record = await store.get_authorized_session(created.session_id, created.session_token)
        before = [agent.model_dump() for agent in record.audiences]
        with pytest.raises(EvaluationProviderError):
            await update_pipeline(
                session_id=created.session_id,
                token=created.session_token,
                request_id=uuid4(),
                expected_step=0,
                context=SegmentContext(client_time_s=1.0),
                audio_path=tmp_path / "unused.wav",
                stt_provider=STTProvider(),
                evaluation_provider=FailingEvaluation(),
                store=store,
            )
        assert record.step == 0
        assert [agent.model_dump() for agent in record.audiences] == before

    asyncio.run(scenario())


def test_fastapi_start_read_and_update_contract(monkeypatch) -> None:
    async def fake_transcribe(*args, **kwargs):
        return STTProvider().transcribe("unused", "ko-KR")

    async def fake_evaluate(**kwargs):
        evaluation = MtDtEvaluation(
            move="Purpose",
            content=ContentScores(
                organization=0.2,
                supporting_material=0.1,
                central_message=0.3,
                cer_validity=0.1,
            ),
            delivery=DeliveryScores(
                language_clarity=0.4,
                vocal_delivery=0.2,
                gaze_delivery=0.0,
                slide_speech_alignment=0.0,
            ),
            segment_note="목적 설명",
            short_reason="명확함",
            missing_inputs=["gaze_delivery_score", "slide_context"],
            confidence=0.8,
        )
        metrics = SpeechMetrics(
            duration_s=0.5,
            word_count=1,
            speech_rate_wps=2.0,
            pause_count=0,
            pause_total_s=0.0,
            filler_count=0,
            repeated_word_count=0,
            avg_confidence=0.95,
            vocal_delivery_score=0.2,
        )
        return evaluation, metrics, []

    monkeypatch.setattr("odi.EVC.pipeline.transcribe_audio", fake_transcribe)
    monkeypatch.setattr("odi.EVC.pipeline.evaluate_presentation_segment", fake_evaluate)

    async def scenario() -> None:
        app = FastAPI()
        app.include_router(router, prefix="/odi")
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            start = await client.post(
                "/odi/xreal_rehear/evc/smart-start",
                data={"presentation_title": "API 테스트", "seed": "10"},
            )
            assert start.status_code == 200, start.text
            started = start.json()
            assert len(started["audiences"]) == 6
            headers = {"X-EVC-Session-Token": started["session_token"]}

            unauthorized = await client.get(
                f"/odi/xreal_rehear/evc/sessions/{started['session_id']}"
            )
            assert unauthorized.status_code == 401
            read = await client.get(
                f"/odi/xreal_rehear/evc/sessions/{started['session_id']}",
                headers=headers,
            )
            assert read.status_code == 200

            update = await client.post(
                "/odi/xreal_rehear/evc/update",
                headers=headers,
                data={
                    "session_id": started["session_id"],
                    "request_id": str(uuid4()),
                    "expected_step": "0",
                    "client_time_s": "1.0",
                    "utterance_position": "utterance_boundary",
                },
                files={"audio": ("voice.wav", b"RIFF-test", "audio/wav")},
            )
            assert update.status_code == 200, update.text
            payload = update.json()
            assert payload["step"] == 1
            assert len(payload["audiences"]) == 6
            assert "commands" in payload

            deleted = await client.delete(
                f"/odi/xreal_rehear/evc/sessions/{started['session_id']}",
                headers=headers,
            )
            assert deleted.status_code == 204
            missing = await client.get(
                f"/odi/xreal_rehear/evc/sessions/{started['session_id']}",
                headers=headers,
            )
            assert missing.status_code == 404

    asyncio.run(scenario())
