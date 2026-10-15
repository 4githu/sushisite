"""Headless playback timing; synthetic clocks/providers, never Unity clock claims."""
import asyncio
import importlib
import json
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from odi.EVC import pipeline
from odi.EVC.reaction_scheduler import AudienceReactionScheduler, ReactionRequest
from odi.EVC.schema import AudienceState, SegmentContext, SmartStartOptions
from odi.EVC.session_store import SessionCapacityError, SessionStore
from odi.EVC.state_engine import initialize_audiences, update_audience_state
from odi.EVC.tests.test_command_pipeline_api import STTProvider, EvaluationProvider
from odi.EVC.tests.test_reaction_scheduler import evidence
from odi.EVC.tests.test_audience_count_contract import api
from odi.EVC.tests.test_answer_service import wav


class Clock:
    def __init__(self, value=1000.):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def make_scheduler(count=6, **kwargs):
    actors = initialize_audiences(SmartStartOptions(presentation_title="Synthetic playback", audience_count=count), 2026)
    return AudienceReactionScheduler(actors, 2026, .5, .5, **kwargs)


def poll(scheduler, now, request_id=None):
    return scheduler.tick(SESSION_ID, ReactionRequest(request_id=request_id or uuid4(), client_time_s=now))


SESSION_ID = uuid4()


async def start(store, independent=False, count=6):
    result = await pipeline.create_pipeline_session(SmartStartOptions(
        presentation_title="Synthetic timing", seed=2026, audience_count=count,
        independent_reactions=independent), store=store)
    record = await store.get_authorized_session(result.session_id, result.session_token)
    return result, record


def update_args(started, step=0, now=30):
    return dict(session_id=started.session_id, token=started.session_token,
        request_id=uuid4(), expected_step=step, context=SegmentContext(client_time_s=now),
        audio_path=Path("synthetic-unused.wav"), stt_provider=STTProvider(), evaluation_provider=EvaluationProvider())


def test_delayed_provider_keeps_evidence_clock():
    async def run():
        clock = Clock()
        class STT(STTProvider):
            def transcribe(self, *args):
                clock.advance(2)
                return super().transcribe(*args)
        class Evaluation(EvaluationProvider):
            def evaluate(self, payload):
                clock.advance(3)
                return super().evaluate(payload)
        store = SessionStore()
        started, record = await start(store)
        args = {**update_args(started), "stt_provider": STT(), "evaluation_provider": Evaluation()}
        response = await pipeline.update_pipeline(**args, store=store, monotonic_clock=clock)
        # Reproduce the existing limitation, not a fabricated retimed fix.
        assert {command.start_time for command in response.commands} == {30.1}
        assert 35 - min(c.start_time for c in response.commands) == pytest.approx(4.9)
        assert record.report_segments[0].client_time_s == 30
        assert record.report_segments[0].context.client_time_s == 30
        assert record.transcript_segments[0].client_time_s == 30
        trace = record.timing_traces[args["request_id"]]
        assert trace.processing_s == 5
        assert trace.stt_s == 2 and trace.evaluation_s == 3
        assert trace.received_monotonic == 1000 and trace.response_ready_monotonic == 1005
        assert trace.evidence_client_time_s == 30
        clock.advance(50)
        retry = await pipeline.update_pipeline(**args, store=store, monotonic_clock=clock)
        assert retry.model_dump() == response.model_dump()
        assert record.timing_traces[args["request_id"]] is trace
    asyncio.run(run())


def test_no_authoritative_playback_clock_is_reported_unknown(caplog):
    async def run():
        store = SessionStore()
        started, record = await start(store)
        args = update_args(started)
        with caplog.at_level("INFO", logger="sushisite.evc"):
            await pipeline.update_pipeline(**args, store=store, monotonic_clock=Clock())
        trace = record.timing_traces[args["request_id"]]
        assert trace.unity_clock_s is None
        assert trace.evidence_age_s is None
        assert trace.playback_clock_source == "unobserved"
        events = [json.loads(item.message) for item in caplog.records if item.message.startswith("{")]
        timing = next(item["timing"] for item in events if item["event"] == "evc_update_completed")
        assert timing["unity_clock_s"] is None and timing["processing_s"] == 0
        assert "Synthetic timing" not in json.dumps(timing)
    asyncio.run(run())


@pytest.mark.parametrize("position", ["slide_transition", "silence_or_pause", "utterance_boundary"])
def test_stale_momentary_event_not_replayed(monkeypatch, position):
    policy = importlib.import_module("odi.EVC.playback_policy").PlaybackPolicy(
        slide_ttl_s=2, pause_ttl_s=2, boundary_ttl_s=2)
    scheduler = make_scheduler(policy=policy)
    fact = evidence(1, -.2, SegmentContext(client_time_s=30, utterance_position=position, slide_reference=True))
    fact.context.event_signals.nearby_interaction = 1
    source = fact.context.model_dump()
    before = {key: listener.agent.model_copy(deep=True) for key, listener in scheduler.listeners.items()}
    seen = []
    module = importlib.import_module("odi.EVC.reaction_scheduler")
    original = module.build_candidate_set
    def candidates(**kwargs):
        seen.append(kwargs["context"].model_dump())
        return original(**kwargs)
    monkeypatch.setattr(module, "build_candidate_set", candidates)
    scheduler.publish(fact)
    emitted = []
    for index in range(20):
        emitted.extend(poll(scheduler, 35 + index * .5).commands)
    assert seen and all(c["utterance_position"] == "during_speech" and not c["slide_reference"] for c in seen)
    assert not any(c.selected_behavior_id.startswith("ACT_") for c in emitted)
    assert fact.context.model_dump() == source
    for key, listener in scheduler.listeners.items():
        expected, _ = update_audience_state(before[key], fact.delta, .5, .5)
        assert listener.agent.state == expected and listener.consumed_step == 1
        assert not listener.pending
    assert any(item["reason"] == "event_expired" and item["source_step"] == 1
               for item in scheduler.playback_drops)


def test_duplicate_poll_keeps_identical_commands():
    scheduler = make_scheduler()
    scheduler.publish(evidence(1, context=SegmentContext(client_time_s=10)))
    request_id = uuid4()
    first = poll(scheduler, 10, request_id)
    assert first.commands
    assessment = scheduler.last_tick_metadata["playback_assessments"][0]
    assert assessment["source_step"] == 1 and assessment["event_age_s"] == 0
    assert assessment["drop_reason"] is None
    assert poll(scheduler, 100000, request_id).model_dump() == first.model_dump()
    assert scheduler.sequence == first.sequence


def test_clock_pause_reset_and_forward_jump():
    module = importlib.import_module("odi.EVC.playback_policy")
    clock = Clock()
    scheduler = make_scheduler(monotonic_clock=clock)
    scheduler.publish(evidence(1, context=SegmentContext(client_time_s=10)))
    first = poll(scheduler, 10)
    state = [(l.agent.model_dump(), list(l.pending)) for l in scheduler.listeners.values()]
    for _ in range(8):
        clock.advance(1)
        assert not poll(scheduler, 10).commands
    assert state == [(l.agent.model_dump(), list(l.pending)) for l in scheduler.listeners.values()]
    for invalid in (0, 100000):
        with pytest.raises(module.PlaybackClockError):
            poll(scheduler, invalid)
        assert scheduler.last_time == 10
    clock.advance(.5)
    assert poll(scheduler, 10.5).audiences
    assert poll(scheduler, 0, first.request_id) == first


@pytest.mark.parametrize("independent", [False, True])
def test_independent_mode_remains_opt_in(independent):
    async def run():
        store = SessionStore()
        started, record = await start(store, independent)
        result = await pipeline.update_pipeline(**update_args(started), store=store)
        assert result.independent_reactions is independent
        assert bool(result.commands) is (not independent)
        if independent:
            assert poll(record.reaction_scheduler, 30).commands
        assert SmartStartOptions(presentation_title="Default mode").independent_reactions is False
    asyncio.run(run())


@pytest.mark.parametrize("count,max_wait", [(1, 0), (6, 2.5), (12, 2.5), (50, 6)])
def test_many_due_actors_are_fair_and_bounded(count, max_wait, tmp_path):
    scheduler = make_scheduler(count)
    for listener in scheduler.listeners.values():
        listener.next_at = 10
    scheduler.publish(evidence(1, context=SegmentContext(client_time_s=10)))
    dispatched = {}
    max_commands = 0
    for index in range(160):
        now = 10 + index * .25
        result = poll(scheduler, now)
        assert len(result.commands) <= 24
        assert len(result.audiences) <= min(4, max(1, (count + 5) // 6))
        max_commands = max(max_commands, len(result.commands))
        for decision in result.audiences:
            assert decision.agent_id not in dispatched
            dispatched[decision.agent_id] = now - 10
    assert set(dispatched) == set(scheduler.listeners)
    assert max(dispatched.values()) <= max_wait
    stats = {"count": count, "first_wait_s": min(dispatched.values()), "last_wait_s": max(dispatched.values()),
             "actor_wait_s": dispatched, "max_commands_in_poll": max_commands}
    (tmp_path / f"due-{count}.json").write_text(json.dumps(stats))
    print(json.dumps(stats, sort_keys=True))


def test_overload_preserves_analysis_order_and_drops_only_stale_playback():
    policy = importlib.import_module("odi.EVC.playback_policy").PlaybackPolicy(max_pending_evidence=2, max_playback_age_s=4)
    async def run():
        store = SessionStore()
        started, record = await start(store, True, 1)
        actors = initialize_audiences(SmartStartOptions(presentation_title="One actor", audience_count=1), 2026)
        record.reaction_scheduler = AudienceReactionScheduler(actors, 2026, .5, .5, policy=policy)
        for step in range(2):
            await pipeline.update_pipeline(**update_args(started, step, 1 + step), store=store)
        with pytest.raises(SessionCapacityError):
            await pipeline.update_pipeline(**update_args(started, 2, 3), store=store)
        assert record.step == 2 and [s.step for s in record.report_segments] == [1, 2]
        listener = next(iter(record.reaction_scheduler.listeners.values()))
        expected = listener.agent.model_copy(deep=True)
        for fact in listener.pending:
            expected.state, _ = update_audience_state(expected, fact.delta, .5, .5)
        result = poll(record.reaction_scheduler, 20)
        assert result.source_steps == [1, 2] and not result.commands
        assert listener.agent.state == expected.state and listener.consumed_step == 2
        assert result.audiences[0].no_op_reason == "stale_playback"
        await pipeline.update_pipeline(**update_args(started, 2, 3), store=store)
        assert record.step == 3 and len(record.report_segments) == 3
        assert not poll(record.reaction_scheduler, 20.5).commands
    asyncio.run(run())


def test_update_admission_bounds_lock_waiters_without_accepting_extra_analysis():
    async def run():
        store = SessionStore(max_pending_updates=2)
        started, record = await start(store)
        tasks = []
        async with record.lock:
            for _ in range(2):
                tasks.append(asyncio.create_task(pipeline.update_pipeline(**update_args(started), store=store)))
                await asyncio.sleep(0)
            with pytest.raises(SessionCapacityError):
                await pipeline.update_pipeline(**update_args(started), store=store)
            assert record.step == 0
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert sum(isinstance(r, pipeline.StepConflictError) for r in results) == 1
        assert record.step == 1 and record.pending_updates == 0
    asyncio.run(run())


def test_timed_out_provider_holds_capacity_until_thread_really_finishes():
    module = importlib.import_module("odi.EVC.provider_execution")
    async def run():
        runner = module.ProviderExecutor(max_workers=1)
        entered, release = threading.Event(), threading.Event()
        def blocked():
            entered.set()
            release.wait(2)
            return "done"
        try:
            task = asyncio.create_task(runner.run(blocked, timeout_s=.02))
            while not entered.is_set():
                await asyncio.sleep(0)
            with pytest.raises(asyncio.TimeoutError):
                await task
            with pytest.raises(module.ProviderCapacityError):
                await runner.run(lambda: "must not run", timeout_s=1)
            release.set()
            while runner.in_flight:
                await asyncio.sleep(0)
            assert await runner.run(lambda: "resumed", timeout_s=1) == "resumed"
        finally:
            release.set()
            runner.close()
    asyncio.run(run())


def test_reaction_http_clock_error_is_409_and_retry_unchanged(monkeypatch):
    routes = importlib.import_module("odi.EVC.router")
    async def run():
        store = SessionStore()
        started, record = await start(store, True)
        monkeypatch.setattr(routes, "session_store", store)
        record.reaction_scheduler.publish(evidence(1, context=SegmentContext(client_time_s=10)))
        app = FastAPI()
        app.include_router(routes.router)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            url = f"/xreal_rehear/evc/sessions/{started.session_id}/reactions"
            headers = {"X-EVC-Session-Token": started.session_token}
            body = {"request_id": str(uuid4()), "client_time_s": 10}
            first = await client.post(url, headers=headers, json=body)
            assert first.status_code == 200
            for value in (0, 100000):
                error = await client.post(url, headers=headers, json={"request_id": str(uuid4()), "client_time_s": value})
                assert error.status_code == 409
            retry = await client.post(url, headers=headers, json={**body, "client_time_s": 100000})
            assert retry.json() == first.json()
            record.presentation_status = "finishing"
            retry_after_finish = await client.post(url, headers=headers, json=body)
            assert retry_after_finish.json() == first.json()
            stopped = await client.post(url, headers=headers, json={**body, "request_id": str(uuid4())})
            assert not stopped.json()["commands"]
            assert len(record.report_reactions) == 1
    asyncio.run(run())


def test_batch_failure_rolls_back_every_actor_rng_and_clock(monkeypatch):
    module = importlib.import_module("odi.EVC.reaction_scheduler")
    scheduler = make_scheduler(12)
    for listener in scheduler.listeners.values():
        listener.next_at = 10
    scheduler.publish(evidence(1, context=SegmentContext(client_time_s=10)))
    def snapshot():
        return {key: (l.agent.model_dump(), list(l.pending), l.next_at,
                      l.choice_rng.getstate(), l.timing_rng.getstate()) for key, l in scheduler.listeners.items()}
    before = snapshot()
    original = module.select_behaviors
    calls = []
    def fail_second(*args):
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("synthetic second-actor failure")
        return original(*args)
    monkeypatch.setattr(module, "select_behaviors", fail_second)
    with pytest.raises(ValueError):
        poll(scheduler, 10)
    assert before == snapshot()
    assert scheduler.last_poll_monotonic is None and scheduler.sequence == 0
    assert not scheduler.cache and scheduler.last_dispatch == -1000


def test_command_budget_defers_whole_actor_without_consuming_evidence(monkeypatch):
    module = importlib.import_module("odi.EVC.reaction_scheduler")
    from odi.EVC.behavior_engine import SelectionResult
    from odi.EVC.schema import BehaviorChoice
    policy = importlib.import_module("odi.EVC.playback_policy").PlaybackPolicy(command_budget=9)
    scheduler = make_scheduler(50, policy=policy)
    for listener in scheduler.listeners.values():
        listener.next_at = 10
    core = BehaviorChoice(behavior_id="BL_01", variation_id="BL_01.neutral_listening", probability=1)
    action = BehaviorChoice(behavior_id="ACT_07", variation_id="ACT_07.self_contact", probability=1)
    monkeypatch.setattr(module, "select_behaviors", lambda *_: SelectionResult(None, None, core, action, None, {}))
    monkeypatch.setattr(module, "limit_synchronized_core_choice", lambda selection, *_args, **_kwargs: selection)
    monkeypatch.setattr(module, "limit_synchronized_action_choice", lambda selection, *_args, **_kwargs: selection)
    scheduler.publish(evidence(1, context=SegmentContext(client_time_s=10)))
    first = poll(scheduler, 10)
    assert len(first.audiences) == 2 and len(first.commands) == 8
    third = scheduler.listeners["audience_03"]
    assert third.consumed_step == 0 and len(third.pending) == 1 and third.next_at == 10
    second = poll(scheduler, 10.5)
    assert second.audiences[0].agent_id == "audience_03"
    assert all(len([c for c in first.commands if c.agent_id == a.agent_id]) == 4 for a in first.audiences)


def test_timing_records_lock_wait_empty_transcript_and_unverified_poll():
    async def run():
        clock = Clock()
        store = SessionStore()
        started, record = await start(store, True)
        poll(record.reaction_scheduler, 35)
        args = update_args(started)
        async with record.lock:
            task = asyncio.create_task(pipeline.update_pipeline(**args, store=store, monotonic_clock=clock))
            await asyncio.sleep(0)
            clock.advance(4)
        response = await task
        trace = record.timing_traces[args["request_id"]]
        assert trace.metadata()["lock_wait_s"] == 4
        assert trace.playback_clock_source == "client_poll_unverified" and trace.evidence_age_s == 5
        assert trace.unity_clock_s is None
        preserved = record.report_segments[0].context.model_dump()
        poll(record.reaction_scheduler, 35.5)
        assert record.report_segments[0].context.model_dump() == preserved
        class Empty(STTProvider):
            def transcribe(self, *args):
                result = super().transcribe(*args)
                return result.model_copy(update={"transcript": "", "words": []})
        args = {**update_args(started, 1, 31), "stt_provider": Empty()}
        result = await pipeline.update_pipeline(**args, store=store, monotonic_clock=clock)
        assert result.no_op_reason == "empty_transcript" and result.step == response.step
        assert record.timing_traces[args["request_id"]].evidence_client_time_s == 31
    asyncio.run(run())


@pytest.mark.parametrize("seam", ["stt", "evaluation"])
def test_real_provider_seams_share_bounded_execution_and_429(monkeypatch, seam):
    execution = importlib.import_module("odi.EVC.provider_execution")
    speech = importlib.import_module("odi.EVC.speech2text")
    evaluation = importlib.import_module("odi.EVC.evaluation")
    routes = importlib.import_module("odi.EVC.router")
    async def run():
        runner = execution.ProviderExecutor(max_workers=1)
        entered, release = threading.Event(), threading.Event()
        def blocked():
            entered.set()
            release.wait(2)
        monkeypatch.setattr(speech, "provider_executor", runner)
        monkeypatch.setattr(evaluation, "provider_executor", runner)
        task = asyncio.create_task(runner.run(blocked, timeout_s=1))
        try:
            while not entered.is_set():
                await asyncio.sleep(0)
            with pytest.raises(execution.ProviderCapacityError) as error:
                if seam == "stt":
                    await speech.transcribe_audio("synthetic-unused.wav", provider=STTProvider())
                else:
                    await evaluation.request_segment_evaluation({}, provider=EvaluationProvider())
            assert routes._http_error(error.value).status_code == 429
        finally:
            release.set()
            await task
            runner.close()
    asyncio.run(run())


def test_continuous_evidence_cannot_starve_due_actors():
    scheduler = make_scheduler(50)
    for listener in scheduler.listeners.values():
        listener.next_at = 10
    seen = set()
    for index in range(28):
        now = 10 + index * .25
        scheduler.publish(evidence(index + 1, .01, SegmentContext(client_time_s=now)))
        result = poll(scheduler, now)
        seen.update(a.agent_id for a in result.audiences)
        assert len(result.commands) <= 24
    assert seen == set(scheduler.listeners)


def test_fresh_pause_event_still_admits_atomic_rear_pair(monkeypatch):
    module = importlib.import_module("odi.EVC.reaction_scheduler")
    from odi.EVC.behavior_engine import SelectionResult
    from odi.EVC.schema import BehaviorChoice
    choice = BehaviorChoice(behavior_id="ACT_08", variation_id="ACT_08.side_conversation", probability=1)
    monkeypatch.setattr(module, "select_behaviors", lambda *_: SelectionResult("E", "negative", None, choice, None, {}))
    scheduler = make_scheduler()
    rear = [l for l in scheduler.listeners.values() if l.agent.profile.row == "rear"]
    for listener in rear:
        listener.agent.state = AudienceState(E=-.7, V=-.7, C=0)
    fact = evidence(1, 0, SegmentContext(client_time_s=30, utterance_position="silence_or_pause"))
    fact.context.event_signals.nearby_interaction = 1
    rear[0].pending.append(fact)
    _, commands = scheduler._evaluate(rear[0], 31)
    assert {c.agent_id for c in commands} == {l.agent.agent_id for l in rear}
    assert len({c.sync_group for c in commands}) == 1
    assert {c.start_time for c in commands} == {31.1}


def test_http_update_admission_and_cached_retry_bypass_full_queue(api):
    app, store, _, _, _, _ = api
    async def run():
        store.max_pending_updates = 1
        started, record = await start(store)
        headers = {"X-EVC-Session-Token": started.session_token}
        body = {"session_id": str(started.session_id), "request_id": str(uuid4()),
                "expected_step": "0", "client_time_s": "10"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def send(data):
                return await client.post("/xreal_rehear/evc/update", headers=headers, data=data,
                    files={"audio": ("synthetic.wav", wav(), "audio/wav")})
            first = await send(body)
            assert first.status_code == 200
            async with record.lock:
                waiting = asyncio.create_task(send({**body, "request_id": str(uuid4()), "expected_step": "1", "client_time_s": "11"}))
                while record.pending_updates == 0:
                    await asyncio.sleep(0)
                refused = await send({**body, "request_id": str(uuid4()), "expected_step": "1"})
                assert refused.status_code == 429
                retry = await asyncio.wait_for(send(body), .5)
                assert retry.json() == first.json()
            assert (await waiting).status_code == 200
            assert record.step == 2 and len(record.report_segments) == 2
    asyncio.run(run())


@pytest.mark.parametrize("seam", ["stt", "evaluation"])
def test_timeout_followed_by_full_capacity_preserves_original_provider_error(monkeypatch, seam):
    execution = importlib.import_module("odi.EVC.provider_execution")
    speech = importlib.import_module("odi.EVC.speech2text")
    evaluation = importlib.import_module("odi.EVC.evaluation")
    async def run():
        runner = execution.ProviderExecutor(max_workers=1)
        release = threading.Event()
        class STT(STTProvider):
            def transcribe(self, *args):
                release.wait(2)
                return super().transcribe(*args)
        class Evaluation(EvaluationProvider):
            def evaluate(self, payload):
                release.wait(2)
                return super().evaluate(payload)
        monkeypatch.setattr(speech, "provider_executor", runner)
        monkeypatch.setattr(evaluation, "provider_executor", runner)
        try:
            if seam == "stt":
                with pytest.raises(speech.STTProviderError):
                    await speech.transcribe_audio("synthetic-unused.wav", provider=STT(), timeout_s=.02, retries=1)
            else:
                with pytest.raises(evaluation.EvaluationProviderError):
                    await evaluation.request_segment_evaluation({}, provider=Evaluation(), timeout_s=.02, retries=1)
            assert runner.in_flight == 1
        finally:
            release.set()
            while runner.in_flight:
                await asyncio.sleep(0)
            runner.close()
    asyncio.run(run())
