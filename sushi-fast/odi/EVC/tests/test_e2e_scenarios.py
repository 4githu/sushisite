import pytest
from fastapi import FastAPI

from odi.EVC.behavior_engine import build_candidate_set
from odi.EVC.clip_pool import load_clip_pool
from odi.EVC.router import router
from odi.EVC.schema import (
    AudienceProfile,
    AudienceRuntimeState,
    AudienceState,
    ChannelPreference,
    EventSignals,
    SegmentContext,
    SpeechMetrics,
)


def make_agent(
    state: AudienceState,
    *,
    agent_id: str = "audience_01",
    row: str = "front",
    has_laptop: bool = False,
) -> AudienceRuntimeState:
    return AudienceRuntimeState(
        agent_id=agent_id,
        profile=AudienceProfile(
            row=row,
            seat="left",
            has_laptop=has_laptop,
            responsiveness=0.6,
            expressivity=0.5,
            critical_bias=0.5,
            channel_preference=ChannelPreference(Face=0.3, Body=0.3, GazeHead=0.4),
        ),
        state=state,
    )


def speech_metrics(word_count: int = 10) -> SpeechMetrics:
    return SpeechMetrics(
        duration_s=10.0,
        word_count=word_count,
        speech_rate_wps=word_count / 10.0,
        pause_count=0,
        pause_total_s=0.0,
        filler_count=0,
        repeated_word_count=0,
        avg_confidence=0.9,
        vocal_delivery_score=0.2,
    )


@pytest.mark.parametrize(
    (
        "expected",
        "state",
        "position",
        "signals",
        "has_laptop",
        "agent_id",
        "row",
        "word_count",
    ),
    [
        (
            "ACT_01.laptop_typing",
            AudienceState(E=0.5, V=0.0, C=-0.8),
            "during_speech",
            EventSignals(information_dense=1.0),
            True,
            "audience_01",
            "front",
            10,
        ),
        (
            "ACT_02.photo_slide",
            AudienceState(E=0.5, V=0.0, C=-0.8),
            "slide_transition",
            EventSignals(slide_reference=1.0),
            False,
            "audience_01",
            "front",
            10,
        ),
        (
            "ACT_03.device_checking",
            AudienceState(E=-0.8, V=0.0, C=0.0),
            "during_speech",
            EventSignals(repeated_disengagement=1.0),
            False,
            "audience_01",
            "front",
            10,
        ),
        (
            "ACT_04.drowsy_nod",
            AudienceState(E=-0.8, V=0.0, C=0.0),
            "silence_or_pause",
            EventSignals(low_arousal=1.0),
            False,
            "audience_01",
            "front",
            10,
        ),
        (
            "ACT_05.seat_adjust",
            AudienceState(E=0.0, V=0.0, C=0.0),
            "silence_or_pause",
            EventSignals(long_static_posture=1.0),
            False,
            "audience_01",
            "front",
            10,
        ),
        (
            "ACT_06.small_stretch",
            AudienceState(E=0.0, V=0.0, C=0.0),
            "silence_or_pause",
            EventSignals(long_static_posture=1.0),
            False,
            "audience_01",
            "front",
            10,
        ),
        (
            "ACT_07.self_contact",
            AudienceState(E=0.0, V=-0.8, C=0.0),
            "utterance_boundary",
            EventSignals(tension=1.0),
            False,
            "audience_01",
            "front",
            10,
        ),
        (
            "ACT_08.side_conversation",
            AudienceState(E=-0.8, V=0.0, C=0.0),
            "silence_or_pause",
            EventSignals(nearby_interaction=1.0),
            False,
            "audience_05",
            "rear",
            10,
        ),
    ],
)
def test_every_action_event_can_enter_its_valid_candidate_set(
    expected,
    state,
    position,
    signals,
    has_laptop,
    agent_id,
    row,
    word_count,
) -> None:
    target = make_agent(
        state,
        agent_id=agent_id,
        row=row,
        has_laptop=has_laptop,
    )
    result = build_candidate_set(
        agent=target,
        context=SegmentContext(
            utterance_position=position,
            slide_reference=signals.slide_reference > 0,
            event_signals=signals,
            client_time_s=1.0,
        ),
        catalog=load_clip_pool(),
        speech_metrics=speech_metrics(word_count),
        current_slide_text="",
        delta=AudienceState(E=0.0, V=-0.2 if expected == "ACT_07.self_contact" else 0.0, C=0.0),
        now_s=1.0,
    )
    assert expected in {clip.variation_id for clip in result.actions}


@pytest.mark.parametrize(
    "position",
    ["during_speech", "utterance_boundary", "silence_or_pause", "slide_transition"],
)
def test_all_utterance_positions_produce_only_allowed_or_noop_candidates(position) -> None:
    target = make_agent(AudienceState(E=0.0, V=0.0, C=0.0))
    result = build_candidate_set(
        agent=target,
        context=SegmentContext(utterance_position=position, client_time_s=1.0),
        catalog=load_clip_pool(),
        speech_metrics=speech_metrics(),
        current_slide_text="",
        delta=AudienceState(E=0.0, V=0.0, C=0.0),
        now_s=1.0,
    )
    assert all(position in clip.utterance_positions for clip in result.core)
    assert all(position in clip.utterance_positions for clip in result.actions)


def test_evc_openapi_contains_v2_lifecycle_paths_and_schemas() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/odi")
    schema = app.openapi()
    base = "/odi/xreal_rehear/evc"

    assert "post" in schema["paths"][f"{base}/smart-start"]
    assert {"get", "delete"} <= set(schema["paths"][f"{base}/sessions/{{session_id}}"])
    assert "post" in schema["paths"][f"{base}/update"]
    assert "SmartStartResponseV2" in schema["components"]["schemas"]
    assert "EVCUpdateResponseV2" in schema["components"]["schemas"]
