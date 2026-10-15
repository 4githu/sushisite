import pytest

from odi.EVC.schema import (
    AudienceProfile,
    AudienceRuntimeState,
    AudienceState,
    ChannelPreference,
    ContentScores,
    DeliveryScores,
    MtDtEvaluation,
)
from odi.EVC.state_engine import compute_state_delta, update_audience_state, individual_negative_sensitivity


def evaluation(value: float) -> MtDtEvaluation:
    return MtDtEvaluation(
        move="Purpose",
        content=ContentScores(
            organization=value,
            supporting_material=value,
            central_message=value,
            cer_validity=value,
        ),
        delivery=DeliveryScores(
            language_clarity=value,
            vocal_delivery=value,
            gaze_delivery=value,
            slide_speech_alignment=value,
        ),
        segment_note="",
        short_reason="test",
        confidence=1.0,
    )


def agent(state: AudienceState | None = None) -> AudienceRuntimeState:
    return AudienceRuntimeState(
        agent_id="audience_01",
        profile=AudienceProfile(
            row="front",
            seat="left",
            has_laptop=False,
            responsiveness=0.5,
            expressivity=0.5,
            critical_bias=0.5,
            channel_preference=ChannelPreference(Face=0.3, Body=0.3, GazeHead=0.4),
        ),
        state=state or AudienceState(E=0.0, V=0.0, C=0.0),
    )


def test_positive_maximum_delta_uses_document_weights_and_no_amplification() -> None:
    breakdown = compute_state_delta(evaluation(1.0))
    assert breakdown.content == AudienceState(E=1.0, V=1.0, C=1.0)
    assert breakdown.delivery == AudienceState(E=1.0, V=1.0, C=1.0)
    assert breakdown.common == AudienceState(E=1.0, V=1.0, C=1.0)

    next_state, sensitivity = update_audience_state(
        agent(),
        breakdown.common,
        topic_interest=0.25,
        prior_knowledge=0.25,
    )
    assert sensitivity.model_dump() == {"E": 1.0, "V": 1.0, "C": 1.0}
    assert next_state == AudienceState(E=1.0, V=1.0, C=1.0)


def test_negative_delta_applies_only_e_and_c_setting_sensitivity() -> None:
    breakdown = compute_state_delta(evaluation(-0.2))
    assert breakdown.content.E == pytest.approx(-0.2)
    assert breakdown.content.V == pytest.approx(-0.4)
    assert breakdown.content.C == pytest.approx(-0.6)
    assert breakdown.delivery.E == pytest.approx(-0.5)
    assert breakdown.delivery.V == pytest.approx(-0.3)
    assert breakdown.delivery.C == pytest.approx(-0.4)
    assert breakdown.common.E == pytest.approx(-0.365)
    assert breakdown.common.V == pytest.approx(-0.355)
    assert breakdown.common.C == pytest.approx(-0.5)

    next_state, sensitivity = update_audience_state(
        agent(),
        breakdown.common,
        topic_interest=0.25,
        prior_knowledge=0.75,
    )
    assert sensitivity.model_dump() == {"E": 1.2, "V": 1.0, "C": 0.8}
    assert next_state.E == pytest.approx(-0.438)
    assert next_state.V == pytest.approx(-0.355)
    assert next_state.C == pytest.approx(-0.4)


def test_final_agent_state_is_clamped_after_additive_update() -> None:
    next_state, _ = update_audience_state(
        agent(AudienceState(E=0.9, V=-0.9, C=0.8)),
        AudienceState(E=0.5, V=-0.5, C=0.5),
        topic_interest=0.5,
        prior_knowledge=0.5,
    )
    assert next_state == AudienceState(E=1.0, V=-1.0, C=1.0)


def test_non_contract_setting_is_rejected() -> None:
    with pytest.raises(ValueError):
        update_audience_state(
            agent(),
            AudienceState(E=-0.1, V=0.0, C=0.0),
            topic_interest=0.4,
            prior_knowledge=0.5,
        )


def test_behavior_traits_do_not_change_state_update() -> None:
    common = AudienceState(E=0.2, V=0.2, C=0.2)
    responsive = agent()
    responsive.profile.responsiveness = 0.75
    responsive.profile.critical_bias = 0.75
    reserved = agent()
    reserved.profile.responsiveness = 0.40
    reserved.profile.critical_bias = 0.25

    responsive_state, responsive_sensitivity = update_audience_state(
        responsive,
        common,
        topic_interest=0.5,
        prior_knowledge=0.5,
    )
    reserved_state, reserved_sensitivity = update_audience_state(
        reserved,
        common,
        topic_interest=0.5,
        prior_knowledge=0.5,
    )

    assert responsive_sensitivity == reserved_sensitivity
    assert responsive_state == reserved_state


def test_additive_update_remains_clamped_under_repeated_maximum_input() -> None:
    target = agent()
    maximum = AudienceState(E=1.0, V=1.0, C=1.0)

    for _ in range(100):
        next_state, _ = update_audience_state(target, maximum, 0.5, 0.5)
        target.state = next_state

    assert target.state == AudienceState(E=1.0, V=1.0, C=1.0)


def test_personal_traits_override_population_mean_for_negative_evc_changes():
    low, high = agent(), agent()
    low.profile.topic_interest = .1
    low.profile.prior_knowledge = .2
    high.profile.topic_interest = .9
    high.profile.prior_knowledge = .8
    delta = AudienceState(E=-.2, V=-.2, C=-.2)
    low_state, low_sensitivity = update_audience_state(low, delta, .5, .5)
    high_state, high_sensitivity = update_audience_state(high, delta, .5, .5)
    assert low_state.E < high_state.E
    assert low_state.C < high_state.C
    assert low_state.V == high_state.V
    assert low_sensitivity.E == pytest.approx(1.32)
    assert high_sensitivity.E == pytest.approx(.68)
    # The group mean cannot overwrite a trait already assigned to this actor.
    assert update_audience_state(low, delta, .75, .25)[0] == low_state


@pytest.mark.parametrize("trait,expected", [(0, 1.4), (.25, 1.2), (.5, 1), (.75, .8), (1, .6)])
def test_personal_sensitivity_preserves_original_anchors(trait, expected):
    assert individual_negative_sensitivity(trait) == pytest.approx(expected)


def test_old_profile_without_personal_traits_keeps_legacy_session_behavior():
    original = agent()
    saved = original.model_dump()
    saved["profile"].pop("topic_interest")
    saved["profile"].pop("prior_knowledge")
    restored = AudienceRuntimeState.model_validate(saved)
    assert restored.profile.topic_interest is None
    assert update_audience_state(restored, AudienceState(E=-.2, V=0, C=-.2), .25, .75) == \
        update_audience_state(original, AudienceState(E=-.2, V=0, C=-.2), .25, .75)
