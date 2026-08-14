import asyncio
import time
from pathlib import Path
from uuid import uuid4

from odi.EVC.clip_pool import load_clip_pool
from odi.EVC.pipeline import create_pipeline_session, update_pipeline
from odi.EVC.schema import (
    ContentScores,
    GPTDeliveryScores,
    SegmentContext,
    SegmentEvaluation,
    SmartStartOptions,
    SpeechTextResult,
    SpeechWord,
)
from odi.EVC.session_store import SessionStore


class RehearsalSTT:
    def transcribe(self, file_path, language):
        return SpeechTextResult(
            transcript="Unity 연동 리허설 발표 구간입니다",
            words=[
                SpeechWord(word="Unity", start=0.0, end=0.4, confidence=0.95),
                SpeechWord(word="연동", start=0.5, end=0.9, confidence=0.95),
                SpeechWord(word="리허설", start=1.0, end=1.5, confidence=0.95),
            ],
        )


class RehearsalEvaluation:
    def __init__(self, score: float) -> None:
        self.score = score

    def evaluate(self, payload):
        return SegmentEvaluation(
            move="Purpose",
            content=ContentScores(
                organization=self.score,
                supporting_material=self.score,
                central_message=self.score,
                cer_validity=self.score,
            ),
            delivery=GPTDeliveryScores(
                language_clarity=self.score,
                slide_speech_alignment=0.0,
            ),
            segment_note=f"rehearsal {self.score}",
            short_reason="contract rehearsal",
            missing_inputs=[],
            confidence=1.0,
        )


def test_headless_unity_consumer_rehearses_sequential_timing_and_layer_arbitration(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        store = SessionStore()
        started = await create_pipeline_session(
            SmartStartOptions(
                presentation_title="Unity contract rehearsal",
                seed=2026,
            ),
            store=store,
        )
        catalog = load_clip_pool()
        known_actions = {
            action.action_id
            for clip in [*catalog.core, *catalog.actions]
            for action in clip.unity_actions
        }
        sequence = [
            ("during_speech", 1.0, 0.4),
            ("utterance_boundary", 3.0, 0.4),
            ("silence_or_pause", 5.0, -0.3),
            ("slide_transition", 7.0, -0.3),
        ]
        responses = []
        last_request_id = None
        last_expected_step = None
        for expected_step, (position, client_time, score) in enumerate(sequence):
            request_id = uuid4()
            started_at = time.perf_counter()
            response = await update_pipeline(
                session_id=started.session_id,
                token=started.session_token,
                request_id=request_id,
                expected_step=expected_step,
                context=SegmentContext(
                    utterance_position=position,
                    slide_reference=position == "slide_transition",
                    client_time_s=client_time,
                ),
                audio_path=tmp_path / "mock.wav",
                stt_provider=RehearsalSTT(),
                evaluation_provider=RehearsalEvaluation(score),
                store=store,
            )
            assert time.perf_counter() - started_at < 1.0
            assert response.step == expected_step + 1
            assert len(response.audiences) == 6
            assert all(command.action_id in known_actions for command in response.commands)
            assert all(command.start_time >= client_time for command in response.commands)
            assert all(command.layer in {"Face", "Body", "GazeHead"} for command in response.commands)

            # A Unity consumer groups decomposed layer commands by sync_group.
            sync_keys = {}
            for command in response.commands:
                key = (command.agent_id, command.selected_variation_id, command.priority)
                sync_keys.setdefault(key, set()).add(command.sync_group)
            assert all(len(groups) == 1 for groups in sync_keys.values())

            # If Core and Action target the same layer/time, higher Action priority wins.
            effective = {}
            for command in response.commands:
                key = (command.agent_id, command.layer, command.start_time)
                previous = effective.get(key)
                if previous is None or command.priority > previous.priority:
                    effective[key] = command
            assert all(command.priority in {50, 100} for command in effective.values())
            responses.append(response)
            last_request_id = request_id
            last_expected_step = expected_step

        # Reconnection/duplicate delivery returns the identical cached response.
        replay = await update_pipeline(
            session_id=started.session_id,
            token=started.session_token,
            request_id=last_request_id,
            expected_step=last_expected_step,
            context=SegmentContext(
                utterance_position="slide_transition",
                slide_reference=True,
                client_time_s=7.0,
            ),
            audio_path=tmp_path / "mock.wav",
            stt_provider=RehearsalSTT(),
            evaluation_provider=RehearsalEvaluation(-0.3),
            store=store,
        )
        assert replay == responses[-1]
        record = await store.get_authorized_session(started.session_id, started.session_token)
        assert record.step == 4

        selected = {
            decision.core_behavior.variation_id
            for response in responses
            for decision in response.audiences
            if decision.core_behavior is not None
        }
        assert len(selected) >= 2

    asyncio.run(scenario())
