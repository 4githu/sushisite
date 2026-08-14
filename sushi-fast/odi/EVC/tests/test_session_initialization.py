import asyncio

import pytest

from odi.EVC.schema import SmartStartOptions
from odi.EVC.pipeline import create_pipeline_session, read_pipeline_session
from odi.EVC.session_store import (
    InvalidSessionTokenError,
    SessionCapacityError,
    SessionNotFoundError,
    SessionStore,
)
from odi.EVC.state_engine import create_agent_rngs, initialize_audiences


def options(
    topic_interest: float = 0.5,
    prior_knowledge: float = 0.5,
    seed: int = 1234,
) -> SmartStartOptions:
    return SmartStartOptions(
        presentation_title="Initialization test",
        topic_interest=topic_interest,
        prior_knowledge=prior_knowledge,
        seed=seed,
    )


def test_six_agent_initialization_is_seed_reproducible() -> None:
    first = initialize_audiences(options(), 1234)
    second = initialize_audiences(options(), 1234)

    assert [agent.model_dump() for agent in first] == [agent.model_dump() for agent in second]
    assert [agent.agent_id for agent in first] == [
        f"audience_{index:02d}" for index in range(1, 7)
    ]
    assert sum(agent.profile.has_laptop for agent in first) == 2
    assert sum(agent.profile.has_laptop for agent in first[:4]) == 1
    assert sum(agent.profile.has_laptop for agent in first[4:]) == 1


@pytest.mark.parametrize(
    ("setting", "base"),
    [(0.25, -0.5), (0.5, 0.0), (0.75, 0.5)],
)
def test_initial_e_and_c_follow_settings_with_bounded_offsets(setting: float, base: float) -> None:
    audiences = initialize_audiences(options(setting, setting), 1234)

    for agent in audiences:
        assert base - 0.05 <= agent.state.E <= base + 0.05
        assert base - 0.05 <= agent.state.C <= base + 0.05
        assert agent.state.V == 0.0


def test_rng_map_must_contain_exact_agent_ids() -> None:
    rngs = create_agent_rngs(1234)
    rngs.pop("audience_06")

    with pytest.raises(ValueError):
        initialize_audiences(options(), 1234, rngs=rngs)


def test_session_store_auth_capacity_and_expiry() -> None:
    async def scenario() -> None:
        now = [100.0]
        store = SessionStore(ttl_s=10, max_sessions=1, monotonic_clock=lambda: now[0])
        record, token = await store.create_session(options())

        assert len(record.audiences) == 6
        assert await store.get_authorized_session(record.session_id, token) is record
        with pytest.raises(InvalidSessionTokenError):
            await store.get_authorized_session(record.session_id, "wrong-token")
        with pytest.raises(SessionCapacityError):
            await store.create_session(options(seed=5678))

        now[0] = 111.0
        with pytest.raises(SessionNotFoundError):
            await store.get_authorized_session(record.session_id, token)
        replacement, _ = await store.create_session(options(seed=5678))
        assert replacement.seed == 5678

    asyncio.run(scenario())


def test_session_lock_serializes_mutation() -> None:
    async def scenario() -> None:
        store = SessionStore()
        record, token = await store.create_session(options())
        order: list[str] = []

        async def mutate(label: str) -> None:
            async with store.locked_session(record.session_id, token) as locked:
                order.append(f"{label}-start")
                current = locked.step
                await asyncio.sleep(0)
                locked.step = current + 1
                order.append(f"{label}-end")

        await asyncio.gather(mutate("a"), mutate("b"))
        assert record.step == 2
        assert order in (
            ["a-start", "a-end", "b-start", "b-end"],
            ["b-start", "b-end", "a-start", "a-end"],
        )

    asyncio.run(scenario())


def test_pipeline_session_create_and_read_return_six_agents() -> None:
    async def scenario() -> None:
        store = SessionStore()
        created = await create_pipeline_session(options(), store=store)
        read = await read_pipeline_session(
            created.session_id,
            created.session_token,
            store=store,
        )

        assert created.api_version == "2.0"
        assert len(created.audiences) == 6
        assert len(read.audiences) == 6
        assert read.evc_state == created.initial_evc_state

    asyncio.run(scenario())
