from collections import Counter

import pytest

from odi.EVC.behavior_engine import (
    build_candidate_set,
    commit_selection,
    limit_synchronized_core_choice,
    select_behaviors,
)
from odi.EVC.clip_pool import load_clip_pool
from odi.EVC.command_builder import build_unity_commands
from odi.EVC.schema import (
    AudienceState,
    BehaviorChoice,
    SegmentContext,
    SmartStartOptions,
    SpeechMetrics,
)
from odi.EVC.state_engine import (
    create_agent_rngs,
    initialize_audiences,
    update_audience_state,
)


def run_diversity_scenario(seed: int) -> dict[str, object]:
    rngs = create_agent_rngs(seed)
    agents = initialize_audiences(
        SmartStartOptions(
            presentation_title="diversity acceptance",
            topic_interest=0.75,
            prior_knowledge=0.50,
            seed=seed,
        ),
        seed,
        rngs,
    )
    catalog = load_clip_pool()
    metrics = SpeechMetrics(
        duration_s=5.0,
        word_count=12,
        speech_rate_wps=2.4,
        pause_count=0,
        pause_total_s=0.0,
        filler_count=0,
        repeated_word_count=0,
        avg_confidence=0.95,
        vocal_delivery_score=0.5,
    )
    common_delta = AudienceState(E=0.35, V=0.12, C=0.10)
    behavior_counts: Counter[str] = Counter()
    candidate_sizes: list[int] = []
    maximum_synchronized = 0

    for step in range(30):
        now_s = (step + 1) * 3.0
        utterance_position = (
            "during_speech" if step % 2 == 0 else "utterance_boundary"
        )
        variation_counts: dict[str, int] = {}
        for agent in agents:
            agent.state, _ = update_audience_state(
                agent,
                common_delta,
                0.75,
                0.50,
            )
            candidates = build_candidate_set(
                agent=agent,
                context=SegmentContext(
                    utterance_position=utterance_position,
                    client_time_s=now_s,
                ),
                catalog=catalog,
                speech_metrics=metrics,
                current_slide_text="",
                delta=common_delta,
                now_s=now_s,
            )
            candidate_sizes.append(len(candidates.core))
            selection = select_behaviors(agent, candidates, rngs[agent.agent_id])
            selection = limit_synchronized_core_choice(
                selection,
                candidates,
                variation_counts,
            )
            if selection.core is not None:
                behavior_counts[selection.core.variation_id] += 1
            commit_selection(agent, selection, now_s)
        if variation_counts:
            maximum_synchronized = max(
                maximum_synchronized,
                max(variation_counts.values()),
            )

    return {
        "states": [agent.state.model_dump() for agent in agents],
        "behavior_counts": behavior_counts,
        "candidate_sizes": candidate_sizes,
        "maximum_synchronized": maximum_synchronized,
    }


@pytest.mark.parametrize("seed", [7, 42, 1234, 2026, 98765])
def test_long_running_behavior_selection_meets_diversity_targets(seed: int) -> None:
    result = run_diversity_scenario(seed)
    counts = result["behavior_counts"]
    candidate_sizes = result["candidate_sizes"]

    assert {state["V"] for state in result["states"]} == {1.0}
    assert len(counts) >= 3
    assert max(counts.values()) / sum(counts.values()) <= 0.65
    assert result["maximum_synchronized"] <= 3
    # The specification intentionally exposes one stable AL_01 variation during
    # speech and two transient variations at utterance boundaries.
    assert sum(size == 1 for size in candidate_sizes) / len(candidate_sizes) == 0.50


def test_diversity_scenario_is_seed_reproducible() -> None:
    first = run_diversity_scenario(2026)
    second = run_diversity_scenario(2026)
    assert first == second


def test_same_variation_has_identical_playback_parameters_across_agents() -> None:
    seed = 2026
    agents = initialize_audiences(
        SmartStartOptions(presentation_title="Unity personality", seed=seed),
        seed,
    )
    catalog = load_clip_pool()
    choice = BehaviorChoice(
        behavior_id="BL_01",
        variation_id="BL_01.neutral_listening",
        probability=1.0,
    )
    signatures = {}
    for agent in agents:
        commands = build_unity_commands(
            agent=agent,
            core=choice,
            action=None,
            catalog=catalog,
            context=SegmentContext(client_time_s=10.0),
            accepted_time_s=10.0,
        )
        signatures[agent.agent_id] = (
            commands[0].action_id,
            commands[0].start_time,
            commands[0].intensity,
            commands[0].duration,
        )

    assert set(signatures) == {f"audience_{index:02d}" for index in range(1, 7)}
    assert len(set(signatures.values())) == 1
    assert next(iter(signatures.values())) == (
        "body.neutral_listening",
        10.1,
        1.0,
        2.0,
    )
