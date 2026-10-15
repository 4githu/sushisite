import asyncio
from collections import defaultdict
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from odi.EVC.reaction_scheduler import AudienceReactionScheduler, Evidence, ReactionRequest
from odi.EVC.schema import AudienceState, SegmentContext, SmartStartOptions, SpeechMetrics, EventSignals, BehaviorChoice
from odi.EVC.state_engine import initialize_audiences, update_audience_state
from odi.EVC.session_store import SessionStore
from odi.EVC.pipeline import create_pipeline_session, update_pipeline
from odi.EVC.tests.test_command_pipeline_api import STTProvider, EvaluationProvider


def scheduler(seed=42):
    options = SmartStartOptions(presentation_title="Shared talk", seed=seed)
    return AudienceReactionScheduler(initialize_audiences(options, seed), seed, .5, .5)


def evidence(step, delta=.1, context=None):
    return Evidence(step, AudienceState(E=delta, V=delta, C=delta),
                    context or SegmentContext(client_time_s=step), SpeechMetrics(
                        duration_s=3, word_count=10, speech_rate_wps=3.3,
                        pause_count=0, pause_total_s=0, filler_count=0,
                        repeated_word_count=0, avg_confidence=.95, vocal_delivery_score=0), "")


def tick(s, now, session=None):
    return s.tick(session or uuid4(), ReactionRequest(request_id=uuid4(), client_time_s=now))


def test_independent_clocks_vary_across_listeners_and_cycles():
    s = scheduler()
    times = defaultdict(list)
    for i in range(240):
        if i % 4 == 0:
            s.publish(evidence(i // 4 + 1, .02))
        response = tick(s, i * .25)
        assert len(response.audiences) <= 1
        for decision in response.audiences:
            times[decision.agent_id].append(i * .25)
    assert len(times) == 6
    assert min(map(len, times.values())) >= 9
    assert len({t[0] for t in times.values()}) == 6
    for t in times.values():
        assert len({round(b - a, 2) for a, b in zip(t, t[1:])}) >= 2


def test_retry_silence_and_provider_stall_do_not_reapply_evidence_or_burst():
    s = scheduler()
    originals = {k: l.agent.model_copy(deep=True) for k, l in s.listeners.items()}
    s.publish(evidence(1))
    s.publish(evidence(1))  # Duplicate upload delivery.
    session = uuid4()
    request = ReactionRequest(request_id=uuid4(), client_time_s=100)
    response = s.tick(session, request)
    assert len(response.audiences) == 1
    assert response.source_steps == [1]
    assert s.tick(session, request) == response
    assert tick(s, 100).audiences == []
    for i in range(1, 120):
        tick(s, 100 + i * .25)
    for key, listener in s.listeners.items():
        expected, _ = update_audience_state(originals[key], evidence(1).delta, .5, .5)
        assert listener.agent.state == expected
        assert listener.consumed_step == 1
        assert not listener.pending


def test_multiple_unseen_deltas_are_applied_in_order_once():
    s = scheduler()
    expected = {k: l.agent.model_copy(deep=True) for k, l in s.listeners.items()}
    for step, delta in enumerate([.8, .6, -.8, .1], 1):
        fact = evidence(step, delta)
        s.publish(fact)
        for agent in expected.values():
            agent.state, _ = update_audience_state(agent, fact.delta, .5, .5)
    for i in range(80):
        tick(s, i * .25)
    assert {k: l.agent.state for k, l in s.listeners.items()} == {k: a.state for k, a in expected.items()}


def test_selection_failure_rolls_back_consumption_and_random_state(monkeypatch):
    import odi.EVC.reaction_scheduler as module
    s = scheduler()
    s.publish(evidence(1))
    before = {k: (l.agent.state.model_dump(), l.choice_rng.getstate(), l.next_at)
              for k, l in s.listeners.items()}
    def fail(*args):
        raise ValueError("Broken clip mapping")
    monkeypatch.setattr(module, "select_behaviors", fail)
    with pytest.raises(ValueError):
        tick(s, 100)
    for key, listener in s.listeners.items():
        assert (listener.agent.state.model_dump(), listener.choice_rng.getstate(), listener.next_at) == before[key]
        assert len(listener.pending) == 1 and listener.consumed_step == 0
    assert not s.cache


def test_small_changes_hold_core_but_large_changes_can_interrupt(monkeypatch):
    import odi.EVC.reaction_scheduler as module
    from odi.EVC.behavior_engine import SelectionResult
    s = scheduler()
    listener = next(iter(s.listeners.values()))
    listener.current_core = "BL_03.quiet_stable_posture"
    listener.core_state = listener.agent.state.model_copy()
    listener.last_core_at = 10
    choice = BehaviorChoice(behavior_id="BL_01", variation_id="BL_01.neutral_listening", probability=1)
    monkeypatch.setattr(module, "select_behaviors", lambda *args: SelectionResult(None, None, choice, None, None, {}))
    listener.pending.append(evidence(1, .01))
    decision, commands = s._evaluate(listener, 11)
    assert decision.core_behavior is None
    assert not commands
    listener.pending.append(evidence(2, -.6))
    decision, commands = s._evaluate(listener, 12)
    assert decision.core_behavior == choice
    assert commands  # No wait for a previous clip duration/max-hold timer.


def test_side_conversation_is_atomic_rear_pair_and_partner_must_qualify(monkeypatch):
    import odi.EVC.reaction_scheduler as module
    from odi.EVC.behavior_engine import SelectionResult
    choice = BehaviorChoice(behavior_id="ACT_08", variation_id="ACT_08.side_conversation", probability=1)
    monkeypatch.setattr(module, "select_behaviors", lambda *args: SelectionResult("E", "negative", None, choice, None, {}))
    s = scheduler()
    rear = [l for l in s.listeners.values() if l.agent.profile.row == "rear"]
    for listener in rear:
        listener.agent.state = AudienceState(E=-.7, V=-.7, C=0)
    fact = evidence(1, 0, SegmentContext(client_time_s=10, utterance_position="silence_or_pause",
        event_signals=EventSignals(nearby_interaction=1)))
    rear[0].pending.append(fact)
    _, commands = s._evaluate(rear[0], 10)
    assert {c.agent_id for c in commands} == {l.agent.agent_id for l in rear}
    assert len({c.sync_group for c in commands}) == 1
    assert len({c.start_time for c in commands}) == 1
    rear[0].pending.append(evidence(2, 0, fact.context))
    _, commands = s._evaluate(rear[0], 11)
    assert not commands  # Partner cooldown also prevents unilateral repeat.


def test_pipeline_opt_in_keeps_report_complete_and_polls_do_not_wait_for_analysis_lock(tmp_path, monkeypatch):
    import importlib
    routes = importlib.import_module("odi.EVC.router")
    async def scenario():
        store = SessionStore()
        monkeypatch.setattr(routes, "session_store", store)
        created = await create_pipeline_session(SmartStartOptions(
            presentation_title="Test", seed=8, independent_reactions=True), store=store)
        assert created.independent_reactions
        response = await update_pipeline(session_id=created.session_id, token=created.session_token,
            request_id=uuid4(), expected_step=0, context=SegmentContext(client_time_s=10),
            audio_path=tmp_path / "unused.wav", stt_provider=STTProvider(),
            evaluation_provider=EvaluationProvider(), store=store)
        assert response.independent_reactions and not response.commands
        record = await store.get_authorized_session(created.session_id, created.session_token)
        assert record.report_segments[0].evaluation == response.evaluation
        app = FastAPI()
        app.include_router(routes.router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            url = f"/xreal_rehear/evc/sessions/{created.session_id}/reactions"
            body = {"request_id": str(uuid4()), "client_time_s": 20}
            assert (await client.post(url, json=body)).status_code == 401
            async with record.lock:
                result = await asyncio.wait_for(client.post(url, json=body,
                    headers={"X-EVC-Session-Token": created.session_token}), 1)
            assert result.status_code == 200, result.text
            assert len(result.json()["audiences"]) == 1
            retry = await client.post(url, json=body, headers={"X-EVC-Session-Token": created.session_token})
            assert retry.json() == result.json()
            record.presentation_status = "finishing"
            stopped = await client.post(url, json={**body, "request_id": str(uuid4())},
                headers={"X-EVC-Session-Token": created.session_token})
            assert not stopped.json()["commands"]
    asyncio.run(scenario())
