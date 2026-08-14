import math
import random

import pytest

from odi.EVC.behavior_engine import (
    build_candidate_set,
    commit_selection,
    preference_score,
    sample_categorical,
    score_core_candidate,
    select_behaviors,
    softmax,
)
from odi.EVC.clip_pool import load_clip_pool
from odi.EVC.schema import (
    AudienceProfile,
    AudienceRuntimeState,
    AudienceState,
    ChannelPreference,
    SegmentContext,
    SpeechMetrics,
)


def agent(state: AudienceState, critical_bias: float = 0.5) -> AudienceRuntimeState:
    return AudienceRuntimeState(
        agent_id="audience_01",
        profile=AudienceProfile(
            row="front",
            seat="left",
            has_laptop=False,
            responsiveness=0.6,
            expressivity=0.5,
            critical_bias=critical_bias,
            channel_preference=ChannelPreference(Face=0.3, Body=0.3, GazeHead=0.4),
        ),
        state=state,
    )


def metrics() -> SpeechMetrics:
    return SpeechMetrics(
        duration_s=5.0,
        word_count=10,
        speech_rate_wps=2.0,
        pause_count=0,
        pause_total_s=0.0,
        filler_count=0,
        repeated_word_count=0,
        avg_confidence=0.9,
        vocal_delivery_score=0.5,
    )


def candidate_set(target: AudienceRuntimeState, context: SegmentContext):
    return build_candidate_set(
        agent=target,
        context=context,
        catalog=load_clip_pool(),
        speech_metrics=metrics(),
        current_slide_text="",
        delta=AudienceState(E=0.0, V=0.0, C=0.0),
        now_s=context.client_time_s,
    )


def test_softmax_is_stable_and_categorical_matches_distribution() -> None:
    probabilities = softmax([1000.0, 1000.0 + math.log(3.0)])
    assert probabilities[0] == pytest.approx(0.25)
    assert probabilities[1] == pytest.approx(0.75)

    rng = random.Random(42)
    counts = [0, 0]
    for _ in range(5000):
        counts[sample_categorical(probabilities, rng)] += 1
    assert abs(counts[0] / 5000 - 0.25) < 0.03
    assert abs(counts[1] / 5000 - 0.75) < 0.03


def test_same_seed_and_input_select_the_same_core_from_candidates() -> None:
    target = agent(AudienceState(E=0.8, V=0.2, C=0.3))
    candidates = candidate_set(
        target,
        SegmentContext(utterance_position="utterance_boundary", client_time_s=10.0),
    )
    first = select_behaviors(target, candidates, random.Random(1234))
    second = select_behaviors(target, candidates, random.Random(1234))

    assert first == second
    if first.core is not None:
        assert first.core.variation_id in {clip.variation_id for clip in candidates.core}


def test_commit_updates_only_actual_choices_and_enforces_bounded_history() -> None:
    target = agent(AudienceState(E=0.8, V=0.2, C=0.3))
    candidates = candidate_set(target, SegmentContext(client_time_s=10.0))
    selection = select_behaviors(target, candidates, random.Random(4))

    commit_selection(target, selection, 10.0)
    assert target.previous_dominant_axis == "E"
    assert selection.core is not None
    assert target.cooldowns[selection.core.variation_id] == 10.0
    assert target.core_history[-1].variation_id == selection.core.variation_id

    for step in range(1, 12):
        commit_selection(target, selection, 10.0 + step)
    assert len(target.core_history) == 8


def test_critical_bias_changes_only_critical_negative_preference() -> None:
    low_bias = agent(AudienceState(E=0.2, V=-0.8, C=0.2), critical_bias=0.25)
    high_bias = agent(AudienceState(E=0.2, V=-0.8, C=0.2), critical_bias=0.75)
    assert preference_score(high_bias, 0.5, critical=True) > preference_score(
        low_bias, 0.5, critical=True
    )

    positive_low = agent(AudienceState(E=0.2, V=0.8, C=0.2), critical_bias=0.25)
    positive_high = agent(AudienceState(E=0.2, V=0.8, C=0.2), critical_bias=0.75)
    assert preference_score(positive_low, 0.5, critical=True) == preference_score(
        positive_high, 0.5, critical=True
    )


def test_selection_returns_at_most_one_action_overlay() -> None:
    target = agent(AudienceState(E=-0.8, V=-0.8, C=-0.8))
    target.consecutive_low_engagement = 2
    target.consecutive_low_arousal = 3
    candidates = candidate_set(
        target,
        SegmentContext(utterance_position="silence_or_pause", client_time_s=50.0),
    )
    selection = select_behaviors(target, candidates, random.Random(1))

    assert selection.action is None or selection.action.variation_id in {
        clip.variation_id for clip in candidates.actions
    }
    assert not isinstance(selection.action, list)


def test_baseline_fallback_scores_neutrally_when_trigger_does_not_match() -> None:
    target = agent(AudienceState(E=0.9, V=0.9, C=0.9))
    baseline = next(
        clip
        for clip in load_clip_pool().core
        if clip.variation_id == "BL_03.quiet_stable_posture"
    )

    score, diagnostics = score_core_candidate(target, baseline, "E", "positive")

    assert math.isfinite(score)
    assert diagnostics["state_fit"] == 0.5
