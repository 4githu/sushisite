from uuid import uuid4

import pytest
from pydantic import ValidationError

from odi.EVC.schema import (
    AudienceProfile,
    AudienceSnapshot,
    AudienceState,
    ChannelPreference,
    ClipPoolCatalog,
    CoreClipSpec,
    EventSignals,
    SmartStartResponseV2,
    StateCondition,
    UnityActionSpec,
    UnityCommand,
)


def make_preference() -> ChannelPreference:
    return ChannelPreference(Face=0.3, Body=0.3, GazeHead=0.4)


def make_profile() -> AudienceProfile:
    return AudienceProfile(
        row="front",
        seat="left",
        has_laptop=False,
        responsiveness=0.5,
        expressivity=0.5,
        critical_bias=0.5,
        channel_preference=make_preference(),
    )


def make_audiences() -> list[AudienceSnapshot]:
    return [
        AudienceSnapshot(
            agent_id=f"audience_{index:02d}",
            profile=make_profile(),
            state=AudienceState(E=0.0, V=0.0, C=0.0),
        )
        for index in range(1, 7)
    ]


def test_audience_state_clamps_finite_values_and_rejects_nan() -> None:
    state = AudienceState(E=2.0, V=-2.0, C=0.25)
    assert state.model_dump() == {"E": 1.0, "V": -1.0, "C": 0.25}

    with pytest.raises(ValidationError):
        AudienceState(E=float("nan"), V=0.0, C=0.0)


def test_channel_preference_requires_normalized_finite_weights() -> None:
    assert make_preference().model_dump(by_alias=True) == {
        "Face": 0.3,
        "Body": 0.3,
        "GazeHead": 0.4,
    }

    with pytest.raises(ValidationError):
        ChannelPreference(Face=0.5, Body=0.5, GazeHead=0.5)


def test_event_signals_reject_unknown_or_out_of_range_values() -> None:
    with pytest.raises(ValidationError):
        EventSignals(unknown_event=1.0)

    with pytest.raises(ValidationError):
        EventSignals(tension=1.1)


def test_clip_schema_enforces_namespaces_layers_and_unique_variations() -> None:
    clip = CoreClipSpec(
        behavior_id="BL_01",
        variation_id="BL_01.neutral_listening",
        parent_group="Baseline Listening",
        trigger_conditions=[StateCondition(E={"mid"}, V={"mid"}, C={"mid"})],
        utterance_positions={"during_speech"},
        channels={"Body", "GazeHead"},
        cooldown_s=2.0,
        expressivity_target=0.3,
        motion_class="stable",
        unity_actions=[
            UnityActionSpec(
                layer="Body",
                action_id="body.neutral_listening",
                duration=2.0,
            ),
            UnityActionSpec(
                layer="GazeHead",
                action_id="gaze_head.neutral_listening",
                duration=2.0,
            ),
        ],
    )
    assert ClipPoolCatalog(core=[clip], actions=[]).core[0].variation_id == clip.variation_id

    with pytest.raises(ValidationError):
        ClipPoolCatalog(core=[clip, clip], actions=[])

    with pytest.raises(ValidationError):
        UnityActionSpec(
            layer="Face",
            action_id="body.namespace_mismatch",
            duration=1.0,
        )


def test_smart_start_response_requires_six_unique_agents() -> None:
    response = SmartStartResponseV2(
        session_id=uuid4(),
        session_token="x" * 32,
        seed=10,
        presentation_title="Contract test",
        initial_evc_state=AudienceState(E=0.0, V=0.0, C=0.0),
        topic_interest=0.5,
        prior_knowledge=0.5,
        audiences=make_audiences(),
        expires_in_s=7200,
        slide_count=0,
        slides=[],
    )
    assert len(response.audiences) == 6

    duplicates = make_audiences()
    duplicates[-1] = duplicates[0]
    with pytest.raises(ValidationError):
        SmartStartResponseV2(
            session_id=uuid4(),
            session_token="x" * 32,
            seed=10,
            presentation_title="Contract test",
            initial_evc_state=AudienceState(E=0.0, V=0.0, C=0.0),
            topic_interest=0.5,
            prior_knowledge=0.5,
            audiences=duplicates,
            expires_in_s=7200,
            slide_count=0,
            slides=[],
        )


def test_unity_command_serializes_the_v2_layer_contract() -> None:
    command = UnityCommand(
        agent_id="audience_01",
        start_time=12.55,
        layer="Body",
        action_id="body.comprehension_nod",
        duration=1.2,
        sync_group=uuid4(),
        selected_behavior_id="CT_01",
        selected_variation_id="CT_01.comprehension_nod",
        priority=50,
        blend_mode="override",
        intensity=0.5,
    )
    assert command.layer == "Body"
    assert command.model_dump(mode="json")["sync_group"]
