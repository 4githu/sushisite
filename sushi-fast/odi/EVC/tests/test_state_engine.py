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
from odi.EVC.state_engine import compute_state_delta, update_audience_state


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
