from __future__ import annotations

import random
import time
from collections import OrderedDict
from uuid import UUID

from .behavior_engine import (
    build_candidate_set,
    commit_selection,
    select_behaviors,
    update_engagement_counters,
)
from .clip_pool import load_clip_pool
from .command_builder import build_unity_commands, commit_command_times
from .config import EVC_INCLUDE_DIAGNOSTICS
from .evaluation import (
    SegmentEvaluationProvider,
    empty_evaluation,
    evaluate_presentation_segment,
)
from .observability import record_update
from .schema import (
    AudienceDecision,
    AudienceSnapshot,
    AudienceState,
    BehaviorCommand,
    EVCUpdateResponseV2,
    SessionResponseV2,
    SegmentContext,
    SlideInfo,
    SpeechMetrics,
    SmartStartOptions,
    SmartStartResponseV2,
    StateDeltaBreakdown,
    StateSensitivity,
)
from .session_store import SessionStore, session_store
from .speech2text import SpeechToTextProvider, transcribe_audio
from .state_engine import aggregate_state, compute_state_delta, update_audience_state


class StepConflictError(RuntimeError):
    pass


class ClientTimeRegressionError(RuntimeError):
    pass


async def create_pipeline_session(
    options: SmartStartOptions,
    slides: list[SlideInfo] | None = None,
    slide_file_path: str | None = None,
    store: SessionStore = session_store,
) -> SmartStartResponseV2:
    record, raw_token = await store.create_session(
        options=options,
        slides=slides,
        slide_file_path=slide_file_path,
    )
    snapshots = [
        AudienceSnapshot(
            agent_id=agent.agent_id,
            profile=agent.profile,
            state=agent.state,
        )
        for agent in record.audiences
    ]
    return SmartStartResponseV2(
        session_id=record.session_id,
        session_token=raw_token,
        seed=record.seed,
        presentation_title=record.presentation_title,
        initial_evc_state=aggregate_state(record.audiences),
        topic_interest=record.topic_interest,
        prior_knowledge=record.prior_knowledge,
        audiences=snapshots,
        expires_in_s=store.expires_in_s(record),
        slide_count=len(record.slides),
        slides=record.slides,
    )


async def read_pipeline_session(
    session_id,
    token: str,
    store: SessionStore = session_store,
) -> SessionResponseV2:
    record = await store.get_authorized_session(session_id, token)
    snapshots = [
        AudienceSnapshot(
            agent_id=agent.agent_id,
            profile=agent.profile,
            state=agent.state,
        )
        for agent in record.audiences
    ]
    return SessionResponseV2(
        session_id=record.session_id,
        presentation_title=record.presentation_title,
        evc_state=aggregate_state(record.audiences),
        audiences=snapshots,
        step=record.step,
        created_at=record.created_at,
        updated_at=record.updated_at,
        expires_in_s=store.expires_in_s(record),
        topic_interest=record.topic_interest,
        prior_knowledge=record.prior_knowledge,
        segment_notes=record.segment_notes,
        slide_count=len(record.slides),
        slides=record.slides,
        warnings=record.warnings,
    )


async def update_pipeline(
    *,
    session_id: UUID,
    token: str,
    request_id: UUID,
    expected_step: int,
    context: SegmentContext,
    audio_path,
    stt_provider: SpeechToTextProvider | None = None,
    evaluation_provider: SegmentEvaluationProvider | None = None,
    store: SessionStore = session_store,
) -> EVCUpdateResponseV2:
    pipeline_started = time.perf_counter()
    catalog = load_clip_pool()
    async with store.locked_session(session_id, token) as record:
        cached = record.request_cache.get(request_id)
        if cached is not None:
            return cached
        if expected_step != record.step:
            raise StepConflictError(
                f"expected_step={expected_step} does not match current step={record.step}"
            )
        if context.client_time_s < record.accepted_client_time_s - 0.25:
            raise ClientTimeRegressionError("client_time_s regressed by more than 0.25 seconds")
        accepted_time = max(context.client_time_s, record.accepted_client_time_s)

        stt_result = await transcribe_audio(
            audio_path,
            context.language,
            provider=stt_provider,
        )
        evaluation, speech_metrics, warnings = await evaluate_presentation_segment(
            presentation_title=record.presentation_title,
            slides=record.slides,
            segment_notes=record.segment_notes,
            stt_result=stt_result,
            context=context,
            provider=evaluation_provider,
        )
        if not stt_result.transcript.strip():
            response = _empty_update_response(
                record=record,
                request_id=request_id,
                context=context,
                accepted_time=accepted_time,
                speech_metrics=speech_metrics,
                evaluation=evaluation,
            )
            record.accepted_client_time_s = accepted_time
            _cache_response(record.request_cache, request_id, response)
            record_update(
                response,
                latency_ms=(time.perf_counter() - pipeline_started) * 1000,
                stt_provider=type(stt_provider).__name__ if stt_provider else "Deepgram",
                evaluation_provider="skipped_empty_transcript",
            )
            return response

        delta = compute_state_delta(evaluation)
        working_agents = [agent.model_copy(deep=True) for agent in record.audiences]
        working_rngs: dict[str, random.Random] = {}
        for agent_id, source_rng in record.rngs.items():
            cloned = random.Random()
            cloned.setstate(source_rng.getstate())
            working_rngs[agent_id] = cloned

        decisions: list[AudienceDecision] = []
        commands = []
        diagnostics: dict[str, object] = {}
        current_slide_text = (
            record.slides[context.current_slide_index].text if record.slides else ""
        )
        for agent in working_agents:
            previous_state = agent.state.model_copy()
            next_state, sensitivity = update_audience_state(
                agent,
                delta.common,
                record.topic_interest,
                record.prior_knowledge,
            )
            agent.state = next_state
            update_engagement_counters(agent)
            candidate_set = build_candidate_set(
                agent=agent,
                context=context,
                catalog=catalog,
                speech_metrics=speech_metrics,
                current_slide_text=current_slide_text,
                delta=delta.common,
                now_s=accepted_time,
            )
            selection = select_behaviors(agent, candidate_set, working_rngs[agent.agent_id])
            agent_commands = build_unity_commands(
                agent=agent,
                core=selection.core,
                action=selection.action,
                catalog=catalog,
                context=context,
                accepted_time_s=accepted_time,
            )
            commit_selection(agent, selection, accepted_time)
            commit_command_times(agent, agent_commands)
            commands.extend(agent_commands)
            decisions.append(
                AudienceDecision(
                    agent_id=agent.agent_id,
                    previous_state=previous_state,
                    sensitivity=sensitivity,
                    state=agent.state,
                    dominant_axis=selection.dominant_axis,
                    direction=selection.direction,
                    core_behavior=selection.core,
                    action_overlay=selection.action,
                    no_op_reason=selection.no_op_reason,
                )
            )
            diagnostics[agent.agent_id] = selection.diagnostics

        aggregate = aggregate_state(working_agents)
        behavior = _legacy_behavior(decisions, commands, catalog)
        next_step = record.step + 1
        response = EVCUpdateResponseV2(
            request_id=request_id,
            session_id=record.session_id,
            step=next_step,
            accepted_client_time_s=accepted_time,
            latest_speech=stt_result.transcript,
            current_slide_index=context.current_slide_index,
            speech_metrics=speech_metrics,
            evaluation=evaluation,
            delta=delta,
            evc_state=aggregate,
            behavior=behavior,
            audiences=decisions,
            commands=commands,
            warnings=warnings,
            diagnostics=diagnostics if EVC_INCLUDE_DIAGNOSTICS else None,
        )

        record.audiences = working_agents
        record.rngs = working_rngs
        record.step = next_step
        record.accepted_client_time_s = accepted_time
        if evaluation.segment_note.strip():
            record.segment_notes.append(evaluation.segment_note.strip())
        record.warnings = warnings
        _cache_response(record.request_cache, request_id, response)
        record_update(
            response,
            latency_ms=(time.perf_counter() - pipeline_started) * 1000,
            stt_provider=type(stt_provider).__name__ if stt_provider else "Deepgram",
            evaluation_provider=(
                type(evaluation_provider).__name__ if evaluation_provider else "OpenAI"
            ),
        )
        return response


def _empty_update_response(
    *,
    record,
    request_id: UUID,
    context: SegmentContext,
    accepted_time: float,
    speech_metrics: SpeechMetrics,
    evaluation,
) -> EVCUpdateResponseV2:
    zero = AudienceState(E=0.0, V=0.0, C=0.0)
    decisions = [
        AudienceDecision(
            agent_id=agent.agent_id,
            previous_state=agent.state,
            sensitivity=StateSensitivity(E=1.0, V=1.0, C=1.0),
            state=agent.state,
            dominant_axis=agent.previous_dominant_axis,
            direction=None,
            core_behavior=None,
            action_overlay=None,
            no_op_reason="empty_transcript",
        )
        for agent in record.audiences
    ]
    return EVCUpdateResponseV2(
        request_id=request_id,
        session_id=record.session_id,
        step=record.step,
        accepted_client_time_s=accepted_time,
        latest_speech="",
        current_slide_index=context.current_slide_index,
        speech_metrics=speech_metrics,
        evaluation=evaluation,
        delta=StateDeltaBreakdown(content=zero, delivery=zero, common=zero),
        evc_state=aggregate_state(record.audiences),
        behavior=None,
        audiences=decisions,
        commands=[],
        warnings=[],
        no_op_reason="empty_transcript",
    )


def _legacy_behavior(decisions, commands, catalog) -> BehaviorCommand | None:
    first = decisions[0]
    if first.core_behavior is None:
        return None
    clip = next(
        clip for clip in catalog.core if clip.variation_id == first.core_behavior.variation_id
    )
    gaze = next(
        (
            command.action_id
            for command in commands
            if command.agent_id == first.agent_id and command.layer == "GazeHead"
        ),
        None,
    )
    return BehaviorCommand(
        selected_behavior_id=first.core_behavior.behavior_id,
        group=clip.parent_group,
        action_overlay=(
            first.action_overlay.variation_id if first.action_overlay is not None else None
        ),
        gaze_head_adjustment=gaze,
        intensity=next(
            (
                command.intensity
                for command in commands
                if command.agent_id == first.agent_id
            ),
            0.0,
        ),
    )


def _cache_response(
    cache: OrderedDict[UUID, object],
    request_id: UUID,
    response: EVCUpdateResponseV2,
) -> None:
    cache[request_id] = response
    cache.move_to_end(request_id)
    while len(cache) > 32:
        cache.popitem(last=False)
