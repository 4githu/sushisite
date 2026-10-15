"""Offline count contract: real ASGI routes, synthetic providers and pre-change goldens."""
import asyncio
import copy
import hashlib
import importlib
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from odi.EVC import pipeline
from odi.EVC.behavior_engine import SelectionResult
from odi.EVC.reaction_scheduler import AudienceReactionScheduler, ReactionRequest
from odi.EVC.schema import (
    AudienceState, BehaviorChoice, QuestionGenerationRequest, SegmentContext,
    SmartStartOptions, TranscriptSegment, AudienceSnapshot, EVCUpdateResponseV2,
    SessionResponseV2, SmartStartResponseV2,
)
from odi.EVC.session_store import SessionStore
from odi.EVC.state_engine import create_agent_rngs, distribute_population_trait, initialize_audiences
from odi.EVC.tests.test_answer_service import Provider as QuestionProvider, wav
from odi.EVC.tests.test_command_pipeline_api import STTProvider, EvaluationProvider
from odi.EVC.tests.test_question_generation import question_set
from odi.EVC.tests.test_reaction_scheduler import evidence


def stable(value):
    """Exclude random transport UUIDs, wall time and machine latency, never behavior."""
    ignored = {"session_id", "request_id", "sync_group", "created_at", "updated_at", "diagnostics"}
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in ignored}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(stable(value), sort_keys=True).encode()).hexdigest()


async def six_golden(seed):
    options = SmartStartOptions(presentation_title="Synthetic six golden", seed=seed)
    rngs = create_agent_rngs(seed)
    actors = initialize_audiences(options, seed, rngs=rngs)
    result = {"initial": [a.model_dump(mode="json") for a in actors],
              "rng_next": {key: [rng.random() for _ in range(4)] for key, rng in rngs.items()}}
    store = SessionStore()
    started = await pipeline.create_pipeline_session(options, store=store)
    updates = []
    for step, position in enumerate(("during_speech", "utterance_boundary", "silence_or_pause", "slide_transition")):
        response = await pipeline.update_pipeline(
            session_id=started.session_id, token=started.session_token,
            request_id=uuid4(), expected_step=step,
            context=SegmentContext(client_time_s=1 + step * 10, utterance_position=position),
            audio_path=Path("synthetic-unused.wav"), stt_provider=STTProvider(),
            evaluation_provider=EvaluationProvider(), store=store)
        updates.append(response.model_dump(mode="json"))
    record = await store.get_authorized_session(started.session_id, started.session_token)
    result["updates_sha256"] = digest(updates)
    result["final_actors_sha256"] = digest([a.model_dump(mode="json") for a in record.audiences])
    result["final_rng_next"] = {key: [rng.random() for _ in range(4)] for key, rng in record.rngs.items()}
    scheduler = AudienceReactionScheduler(actors, seed, .5, .5)
    scheduler.publish(evidence(1, -.3))
    scheduler.publish(evidence(2, .1))
    reactions = [scheduler.tick(uuid4(), ReactionRequest(request_id=uuid4(), client_time_s=i * .5)).model_dump(mode="json")
                 for i in range(50)]
    result["reactions_sha256"] = digest(reactions)
    return result


@pytest.fixture
def api(monkeypatch):
    routes = importlib.import_module("odi.EVC.router")
    store = SessionStore()
    bound = {"template_snapshot": {"audience": {"audience_count": 12}}}
    latest = {"audience": {"audience_count": 50}}
    claims = []
    monkeypatch.setattr(routes, "session_store", store)
    monkeypatch.setattr(routes, "validate_provider_configuration", lambda *_: None)
    monkeypatch.setattr(routes.odidb, "get_pre_session_by_pin", lambda _: {
        "state": "waiting", "session_id": None, "template_id": "synthetic-template", **copy.deepcopy(bound)})
    monkeypatch.setattr(routes.odidb, "get_template", lambda _: {"owner_id": "synthetic-owner", "template": latest})
    monkeypatch.setattr(routes.odidb, "get_user", lambda _: {})
    monkeypatch.setattr(routes.odidb, "claim_pre_session", lambda pin: claims.append(pin))
    monkeypatch.setattr(routes.odidb, "release_pre_session_claim", lambda _: None)
    monkeypatch.setattr(routes.odidb, "upsert_presentation_segment", lambda **_: None)
    async def create(options, **kwargs):
        return await pipeline.create_pipeline_session(options, store=store, **kwargs)
    async def read(*args):
        return await pipeline.read_pipeline_session(*args, store=store)
    async def update(**kwargs):
        return await pipeline.update_pipeline(**kwargs, store=store,
            stt_provider=STTProvider(), evaluation_provider=EvaluationProvider())
    async def tts(*_):
        return wav()
    original_submit = routes.submit_answer
    question_provider = QuestionProvider()
    async def transcribe(_):
        return "Synthetic answer evidence"
    async def submit(**kwargs):
        return await original_submit(**kwargs, store=store, provider=question_provider, transcriber=transcribe)
    monkeypatch.setattr(routes, "create_pipeline_session", create)
    monkeypatch.setattr(routes, "read_pipeline_session", read)
    monkeypatch.setattr(routes, "update_pipeline", update)
    monkeypatch.setattr(routes, "synthesize", tts)
    monkeypatch.setattr(routes, "submit_answer", submit)
    app = FastAPI()
    app.include_router(routes.router)
    return app, store, bound, latest, claims, question_provider


def test_count_resolution_strict_and_missing():
    module = importlib.import_module("odi.EVC.audience_config")
    for snapshot in (None, {}, {"audience": {}}, {"unrelated": 1}):
        assert module.resolve_audience_count(snapshot) == 6
    for count in (1, 6, 12, 50):
        assert module.resolve_audience_count({"audience": {"audience_count": count}}) == count
    for count in (True, False, 3.5, 6.0, "12", None, 0, -1, 51):
        with pytest.raises(ValueError):
            module.resolve_audience_count({"audience": {"audience_count": count}})
        with pytest.raises(ValidationError):
            SmartStartOptions(presentation_title="Strict count", audience_count=count)
    for snapshot in ([], "bad", {"audience": None}, {"audience": []}, {"audience": "bad"}):
        with pytest.raises(ValueError):
            module.resolve_audience_count(snapshot)


def test_pin_uses_bound_snapshot(api):
    app, _, bound, latest, _, _ = api
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            latest["audience"]["audience_count"] = 50
            response = await client.post("/xreal_rehear/evc/smart-start", data={
                "presentation_title": "Bound snapshot", "pre_session_pin": "1234", "seed": "0"})
            assert response.status_code == 200, response.text
            assert len(response.json()["audiences"]) == 12
            for snapshot in (None, {}, {"audience": {}}):
                bound["template_snapshot"] = snapshot
                response = await client.post("/xreal_rehear/evc/smart-start", data={
                    "presentation_title": "Missing count", "pre_session_pin": "1234"})
                assert response.status_code == 200, response.text
                assert len(response.json()["audiences"]) == 6
            response = await client.post("/xreal_rehear/evc/smart-start", data={"presentation_title": "Pinless"})
            assert response.status_code == 200, response.text
            assert len(response.json()["audiences"]) == 6
    asyncio.run(run())


@pytest.mark.parametrize("snapshot", [
    {"audience": {"audience_count": c}} for c in (True, False, 3.5, 6.0, "12", None, 0, -1, 51)
] + [{"audience": None}, {"audience": []}, {"audience": "bad"}, []])
def test_invalid_pin_count_is_422_before_claim(api, snapshot):
    app, _, bound, _, claims, _ = api
    bound["template_snapshot"] = snapshot
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/xreal_rehear/evc/smart-start", data={
                "presentation_title": "Invalid count", "pre_session_pin": "1234"})
            assert response.status_code == 422, response.text
            assert response.json()["detail"]["code"] == "validation_error"
            assert claims == []
    asyncio.run(run())


@pytest.mark.parametrize("count", [1, 3, 6, 12, 50])
def test_population_counts_and_traits(count):
    options = SmartStartOptions(presentation_title="Population", audience_count=count, seed=2026)
    actors = initialize_audiences(options, 2026)
    assert [a.model_dump() for a in actors] == [a.model_dump() for a in initialize_audiences(options, 2026)]
    assert [a.agent_id for a in actors] == [f"audience_{i:02d}" for i in range(1, count + 1)]
    assert set(create_agent_rngs(2026, count)) == {a.agent_id for a in actors}
    assert sum(a.profile.has_laptop for a in actors) == count // 3
    for agent in actors:
        assert agent.profile.row in {"front", "middle", "rear"}
        assert agent.profile.seat in {"left", "right"}
    for setting in (.25, .5, .75):
        configured = options.model_copy(update={"topic_interest": setting, "prior_knowledge": setting})
        configured_actors = initialize_audiences(configured, 2026)
        for field in ("topic_interest", "prior_knowledge"):
            assert sum(getattr(a.profile, field) for a in configured_actors) / count == pytest.approx(setting, abs=1e-12)
    for mean in (0, .5, 1):
        for trait in ("topic_interest", "prior_knowledge"):
            values = distribute_population_trait(mean, 2026, trait, count)
            assert len(values) == count and all(0 <= v <= 1 for v in values)
            assert sum(values) / count == pytest.approx(mean, abs=1e-12)
            assert values == distribute_population_trait(mean, 2026, trait, count)
    with pytest.raises(ValueError):
        initialize_audiences(options, 2026, rngs={})


@pytest.mark.parametrize("seed", [0, 1, 2026])
def test_six_audience_golden_unchanged(seed):
    expected = json.loads(Path(__file__).with_name("fixtures").joinpath("audience_six_golden.json").read_text())
    assert asyncio.run(six_golden(seed)) == expected[str(seed)]


@pytest.mark.parametrize("count", [1, 6, 12, 50])
@pytest.mark.parametrize("independent", [False, True])
def test_start_read_update_return_exact_registry(api, count, independent):
    app, store, bound, _, _, _ = api
    bound["template_snapshot"] = {"audience": {"audience_count": count}}
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/xreal_rehear/evc/smart-start", data={
                "presentation_title": "Registry", "pre_session_pin": "1234", "seed": "2026",
                "independent_reactions": str(independent).lower()})
            assert response.status_code == 200, response.text
            started = response.json()
            ids = [f"audience_{i:02d}" for i in range(1, count + 1)]
            assert [a["agent_id"] for a in started["audiences"]] == ids
            headers = {"X-EVC-Session-Token": started["session_token"]}
            base = f"/xreal_rehear/evc/sessions/{started['session_id']}"
            read = await client.get(base, headers=headers)
            assert read.status_code == 200, read.text
            assert [a["agent_id"] for a in read.json()["audiences"]] == ids
            request = {"session_id": started["session_id"], "request_id": str(uuid4()),
                       "expected_step": "0", "client_time_s": "10"}
            update = await client.post("/xreal_rehear/evc/update", headers=headers, data=request,
                                       files={"audio": ("synthetic.wav", wav(), "audio/wav")})
            assert update.status_code == 200, update.text
            assert [a["agent_id"] for a in update.json()["audiences"]] == ids
            assert all(c["agent_id"] in ids for c in update.json()["commands"])
            replay = await client.post("/xreal_rehear/evc/update", headers=headers, data=request,
                                       files={"audio": ("synthetic.wav", wav(), "audio/wav")})
            assert replay.json() == update.json()
            record = await store.get_authorized_session(UUID(started["session_id"]), started["session_token"])
            assert record.audience_count == count and set(record.rngs) == set(ids)
            if independent:
                seen = set()
                for now in range(20, 20 + count * 2):
                    reaction = await client.post(base + "/reactions", headers=headers,
                        json={"request_id": str(uuid4()), "client_time_s": now})
                    assert reaction.status_code == 200, reaction.text
                    assert all(c["agent_id"] in ids for c in reaction.json()["commands"])
                    seen.update(a["agent_id"] for a in reaction.json()["audiences"])
                assert seen == set(ids)
            else:
                assert update.json()["commands"]
    asyncio.run(run())


@pytest.mark.parametrize("count,invalid,valid", [(1, "audience_02", "audience_01"), (12, "audience_13", "audience_12")])
def test_questions_reject_out_of_session_id(api, count, invalid, valid):
    app, store, _, _, _, provider = api
    async def run():
        record, token = await store.create_session(SmartStartOptions(presentation_title="Questions", audience_count=count))
        record.generated_questions = question_set().questions
        record.transcript_segments = [TranscriptSegment(step=1, client_time_s=1, slide_index=0,
            text="Synthetic presentation evidence", word_count=3)]
        record.question_generation_status = "ready"
        assert QuestionGenerationRequest(request_id=uuid4()).question_count == 3
        for total in (1, 5):
            assert QuestionGenerationRequest(request_id=uuid4(), question_count=total).question_count == total
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = f"/xreal_rehear/evc/sessions/{record.session_id}/questions/0"
            headers = {"X-EVC-Session-Token": token, "X-Speech-Voice": "ko-KR-InJoonNeural"}
            assert (await client.post(base + "/speech", headers={**headers, "X-Audience-Id": invalid})).status_code == 422
            assert (await client.post(base + "/speech", headers={**headers, "X-Audience-Id": valid})).status_code == 200
            for actor, status in ((invalid, 422), (valid, 200)):
                response = await client.post(base + "/answer", headers={**headers,
                    "X-Request-Id": str(uuid4()), "X-Next-Audience-Id": actor}, content=wav())
                assert response.status_code == status, response.text
            assert len(record.generated_questions) == 3
            assert provider.payloads[0]["next_audience"]["agent_id"] == valid
    asyncio.run(run())


def test_last_answer_rejects_supplied_out_of_session_id(api):
    app, store, _, _, _, _ = api
    async def run():
        record, token = await store.create_session(SmartStartOptions(presentation_title="Final answer"))
        record.generated_questions = question_set(1).questions
        record.question_generation_status = "ready"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/xreal_rehear/evc/sessions/{record.session_id}/questions/0/answer",
                headers={"X-EVC-Session-Token": token, "X-Request-Id": str(uuid4()),
                         "X-Next-Audience-Id": "audience_12"}, content=wav())
            assert response.status_code == 422, response.text
            assert not record.qa_answers
    asyncio.run(run())


@pytest.mark.parametrize("count", [1, 3, 6, 12, 15, 50])
def test_rear_pairing_uses_valid_deterministic_partner(monkeypatch, count):
    module = importlib.import_module("odi.EVC.reaction_scheduler")
    choice = BehaviorChoice(behavior_id="ACT_08", variation_id="ACT_08.side_conversation", probability=1)
    monkeypatch.setattr(module, "select_behaviors", lambda *_: SelectionResult("E", "negative", None, choice, None, {}))
    actors = initialize_audiences(SmartStartOptions(presentation_title="Rear pairs", audience_count=count), 2026)
    s = AudienceReactionScheduler(actors, 2026, .5, .5)
    rear = [l for l in s.listeners.values() if l.agent.profile.row == "rear"]
    pairs = {rear[i].agent.agent_id: rear[i ^ 1].agent.agent_id for i in range(len(rear)) if i ^ 1 < len(rear)}
    for key in s.listeners:
        fresh = AudienceReactionScheduler(actors, 2026, .5, .5)
        for listener in fresh.listeners.values():
            listener.agent.state = AudienceState(E=-.8, V=-.8, C=0)
        listener = fresh.listeners[key]
        fact = evidence(1, 0, SegmentContext(client_time_s=10, utterance_position="silence_or_pause"))
        fact.context.event_signals.nearby_interaction = 1
        listener.pending.append(fact)
        _, commands = fresh._evaluate(listener, 10)
        if key in pairs:
            assert {c.agent_id for c in commands} == {key, pairs[key]}
            assert len({c.sync_group for c in commands}) == 1
        else:
            assert not commands


def test_single_actor_has_no_phantom_partner_or_laptop():
    actors = initialize_audiences(SmartStartOptions(presentation_title="Solo", audience_count=1), 0)
    assert len(actors) == 1
    assert not actors[0].profile.has_laptop


@pytest.mark.parametrize("count", [3, 15])
def test_unpaired_rear_cannot_admit_side_conversation(count):
    from odi.EVC.audience_config import bind_audience_catalog
    from odi.EVC.behavior_engine import action_clip_matches
    from odi.EVC.clip_pool import load_clip_pool
    actors = initialize_audiences(SmartStartOptions(presentation_title="Unpaired rear", audience_count=count), 0)
    catalog = bind_audience_catalog(load_clip_pool(), actors)
    clip = next(c for c in catalog.actions if c.behavior_id == "ACT_08")
    rear = [a for a in actors if a.profile.row == "rear"]
    assert len(rear) % 2 == 1
    agent = rear[-1]
    agent.state = AudienceState(E=-.8, V=-.8, C=0)
    context = SegmentContext(client_time_s=10, utterance_position="silence_or_pause")
    context.event_signals.nearby_interaction = 1
    assert not action_clip_matches(clip, agent, context, context.event_signals, "E", "negative", 10)


@pytest.mark.parametrize("count", [1, 12])
@pytest.mark.parametrize("total", [1, 3, 5])
def test_question_total_independent_of_population(count, total):
    from odi.EVC.question_service import generate_session_questions
    async def run():
        store = SessionStore()
        record, token = await store.create_session(SmartStartOptions(
            presentation_title="Independent question total", audience_count=count))
        record.transcript_segments = [TranscriptSegment(step=1, client_time_s=10, slide_index=0,
            text="Synthetic presentation evidence. " * 10, word_count=30)]
        calls = []
        class Provider:
            def generate(self, payload):
                calls.append(payload)
                assert payload["question_count"] == total
                assert len(payload["audience_profiles"]) == count
                return question_set(total)
        result = await generate_session_questions(session_id=record.session_id, token=token,
            request_id=uuid4(), question_count=total, provider=Provider(), store=store)
        assert len(result.questions) == total and len(calls) == 1
        assert [q.order for q in result.questions] == list(range(1, total + 1))
    asyncio.run(run())


def test_response_schemas_reject_invalid_registry_and_command_membership():
    async def run():
        store = SessionStore()
        started = await pipeline.create_pipeline_session(SmartStartOptions(
            presentation_title="Response boundaries", audience_count=1), store=store)
        read = await pipeline.read_pipeline_session(started.session_id, started.session_token, store=store)
        for response, model in ((started, SmartStartResponseV2), (read, SessionResponseV2)):
            original = response.model_dump()
            for ids in ([], ["audience_02"], ["audience_01", "audience_01"], ["audience_00"], ["audience_51"]):
                bad = copy.deepcopy(original)
                bad["audiences"] = [{**original["audiences"][0], "agent_id": actor} for actor in ids]
                with pytest.raises(ValidationError):
                    model.model_validate(bad)
        # Schema format limits and registry membership are separate checks.
        template = started.audiences[0].model_dump()
        assert AudienceSnapshot.model_validate({**template, "agent_id": "audience_50"})
        response = await pipeline.update_pipeline(session_id=started.session_id,
            token=started.session_token, request_id=uuid4(), expected_step=0,
            context=SegmentContext(client_time_s=1), audio_path=Path("synthetic-unused.wav"),
            stt_provider=STTProvider(), evaluation_provider=EvaluationProvider(), store=store)
        bad = response.model_dump()
        assert bad["commands"]
        bad["commands"][0]["agent_id"] = "audience_02"
        with pytest.raises(ValidationError):
            EVCUpdateResponseV2.model_validate(bad)
    asyncio.run(run())
