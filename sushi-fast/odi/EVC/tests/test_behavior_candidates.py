from odi.EVC.behavior_engine import (
    build_candidate_set,
    choose_dominant_axis,
    classify_level,
)
from odi.EVC.clip_pool import load_clip_pool
from odi.EVC.schema import (
    AudienceProfile,
    AudienceRuntimeState,
    AudienceState,
    ChannelPreference,
    EventSignals,
    SegmentContext,
    SpeechMetrics,
)


def agent(
    state: AudienceState,
    *,
    has_laptop: bool = False,
    agent_id: str = "audience_01",
    row: str = "front",
) -> AudienceRuntimeState:
    return AudienceRuntimeState(
        agent_id=agent_id,
        profile=AudienceProfile(
            row=row,
            seat="left",
            has_laptop=has_laptop,
            responsiveness=0.5,
            expressivity=0.5,
            critical_bias=0.5,
            channel_preference=ChannelPreference(Face=0.3, Body=0.3, GazeHead=0.4),
        ),
        state=state,
    )


def metrics(word_count: int = 10) -> SpeechMetrics:
    return SpeechMetrics(
        duration_s=5.0,
        word_count=word_count,
        speech_rate_wps=2.0,
        pause_count=0,
        pause_total_s=0.0,
        filler_count=0,
        repeated_word_count=0,
        avg_confidence=0.9,
        vocal_delivery_score=0.5,
    )


def candidates(
    target: AudienceRuntimeState,
    context: SegmentContext,
    *,
    word_count: int = 10,
    now_s: float = 1.0,
):
    return build_candidate_set(
        agent=target,
        context=context,
        catalog=load_clip_pool(),
        speech_metrics=metrics(word_count),
        current_slide_text="",
        delta=AudienceState(E=0.0, V=0.0, C=0.0),
        now_s=now_s,
    )


def test_state_level_boundaries_are_continuous() -> None:
    assert classify_level(-0.34) == "low"
    assert classify_level(-0.339) == "mid"
    assert classify_level(0.339) == "mid"
    assert classify_level(0.34) == "high"


def test_dominant_axis_baseline_exact_and_near_tie_priorities() -> None:
    assert choose_dominant_axis(AudienceState(E=0.1, V=-0.2, C=0.3)) == (None, None)
    assert choose_dominant_axis(AudienceState(E=0.8, V=0.2, C=0.1)) == ("E", "positive")
    assert choose_dominant_axis(AudienceState(E=0.70, V=-0.72, C=-0.75)) == (
        "C",
        "negative",
    )
    assert choose_dominant_axis(
        AudienceState(E=0.70, V=0.65, C=0.1),
        previous="V",
    ) == ("V", "positive")


def test_core_candidates_apply_state_position_slide_and_cooldown() -> None:
    target = agent(AudienceState(E=0.8, V=0.2, C=0.3))
    during = candidates(target, SegmentContext(client_time_s=1.0))
    assert {clip.variation_id for clip in during.core} == {"AL_01.stable_attention"}

    boundary = candidates(
        target,
        SegmentContext(utterance_position="utterance_boundary", client_time_s=1.0),
    )
    assert {clip.variation_id for clip in boundary.core} == {
        "AL_01.active_following",
        "AL_01.agreement_nod",
    }

    target.cooldowns["AL_01.active_following"] = 0.0
    cooldown = candidates(
        target,
        SegmentContext(utterance_position="utterance_boundary", client_time_s=1.0),
        now_s=1.0,
    )
    assert {clip.variation_id for clip in cooldown.core} == {"AL_01.agreement_nod"}


def test_composite_clip_conditions_route_to_explicit_parent_groups() -> None:
    target = agent(AudienceState(E=0.8, V=-0.7, C=-0.6))
    result = candidates(target, SegmentContext(client_time_s=1.0))
    ids = {clip.variation_id for clip in result.core}

    assert "EM_05.cold_monitoring" in ids
    assert "EM_07.disengaged_negative" in ids
    assert all(clip.parent_group == "Evaluative Monitoring" for clip in result.core)


def test_action_candidates_apply_event_state_and_scene_gates() -> None:
    laptop = agent(AudienceState(E=0.5, V=0.0, C=-0.8), has_laptop=True)
    result = candidates(
        laptop,
        SegmentContext(client_time_s=1.0),
        word_count=45,
    )
    assert "ACT_01.laptop_typing" in {clip.variation_id for clip in result.actions}

    no_laptop = agent(AudienceState(E=0.5, V=0.0, C=-0.8), has_laptop=False)
    result = candidates(
        no_laptop,
        SegmentContext(client_time_s=1.0),
        word_count=45,
    )
    assert "ACT_01.laptop_typing" not in {clip.variation_id for clip in result.actions}

    rear = agent(
        AudienceState(E=-0.8, V=0.0, C=0.1),
        agent_id="audience_05",
        row="rear",
    )
    result = candidates(
        rear,
        SegmentContext(
            utterance_position="silence_or_pause",
            client_time_s=1.0,
            event_signals=EventSignals(nearby_interaction=1.0),
        ),
    )
    assert "ACT_08.side_conversation" in {clip.variation_id for clip in result.actions}


def test_empty_position_candidates_use_no_unsafe_fallback() -> None:
    target = agent(AudienceState(E=0.0, V=0.0, C=0.0))
    result = candidates(
        target,
        SegmentContext(utterance_position="utterance_boundary", client_time_s=1.0),
    )
    assert result.core == ()
    assert result.used_baseline_fallback is False
