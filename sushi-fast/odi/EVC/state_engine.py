from __future__ import annotations

import hashlib
import random

from .schema import (
    AudienceProfile,
    AudienceRuntimeState,
    AudienceState,
    ChannelPreference,
    MtDtEvaluation,
    SmartStartOptions,
    StateDeltaBreakdown,
    StateSensitivity,
    clamp,
)


AUDIENCE_LAYOUT = (
    ("audience_01", "front", "left"),
    ("audience_02", "front", "right"),
    ("audience_03", "middle", "left"),
    ("audience_04", "middle", "right"),
    ("audience_05", "rear", "left"),
    ("audience_06", "rear", "right"),
)


def derive_agent_seed(session_seed: int, agent_id: str) -> int:
    digest = hashlib.sha256(f"{session_seed}:{agent_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def create_agent_rngs(session_seed: int) -> dict[str, random.Random]:
    return {
        agent_id: random.Random(derive_agent_seed(session_seed, agent_id))
        for agent_id, _, _ in AUDIENCE_LAYOUT
    }


def choose_laptop_agents(session_seed: int) -> set[str]:
    session_rng = random.Random(session_seed)
    return {
        session_rng.choice([f"audience_{index:02d}" for index in range(1, 5)]),
        session_rng.choice(["audience_05", "audience_06"]),
    }


def initialize_audiences(
    options: SmartStartOptions,
    seed: int,
    rngs: dict[str, random.Random] | None = None,
) -> list[AudienceRuntimeState]:
    agent_rngs = rngs if rngs is not None else create_agent_rngs(seed)
    expected_ids = {agent_id for agent_id, _, _ in AUDIENCE_LAYOUT}
    if set(agent_rngs) != expected_ids:
        raise ValueError("agent RNG map must contain exactly audience_01 through audience_06")

    laptop_agents = choose_laptop_agents(seed)
    initial_e = (options.topic_interest - 0.50) * 2.0
    initial_c = (options.prior_knowledge - 0.50) * 2.0
    audiences: list[AudienceRuntimeState] = []

    for agent_id, row, seat in AUDIENCE_LAYOUT:
        rng = agent_rngs[agent_id]
        delta_e = rng.uniform(-0.05, 0.05)
        delta_c = rng.uniform(-0.05, 0.05)
        face_raw = rng.uniform(0.20, 1.00)
        body_raw = rng.uniform(0.20, 1.00)
        gaze_raw = rng.uniform(0.20, 1.00)
        channel_total = face_raw + body_raw + gaze_raw
        face = face_raw / channel_total
        body = body_raw / channel_total
        gaze_head = 1.0 - face - body

        profile = AudienceProfile(
            row=row,
            seat=seat,
            has_laptop=agent_id in laptop_agents,
            responsiveness=rng.uniform(0.40, 0.75),
            expressivity=rng.uniform(0.30, 0.70),
            critical_bias=rng.uniform(0.25, 0.75),
            channel_preference=ChannelPreference(
                Face=face,
                Body=body,
                GazeHead=gaze_head,
            ),
        )
        audiences.append(
            AudienceRuntimeState(
                agent_id=agent_id,
                profile=profile,
                state=AudienceState(E=initial_e + delta_e, V=0.0, C=initial_c + delta_c),
            )
        )

    return audiences


def aggregate_state(audiences: list[AudienceRuntimeState]) -> AudienceState:
    if not audiences:
        raise ValueError("cannot aggregate an empty audience")
    count = len(audiences)
    return AudienceState(
        E=sum(agent.state.E for agent in audiences) / count,
        V=sum(agent.state.V for agent in audiences) / count,
        C=sum(agent.state.C for agent in audiences) / count,
    )


def compute_state_delta(evaluation: MtDtEvaluation) -> StateDeltaBreakdown:
    org = evaluation.content.organization
    sup = evaluation.content.supporting_material
    msg = evaluation.content.central_message
    cer = evaluation.content.cer_validity
    lang = evaluation.delivery.language_clarity
    vocal = evaluation.delivery.vocal_delivery
    gaze = evaluation.delivery.gaze_delivery
    align = evaluation.delivery.slide_speech_alignment

    content = AudienceState(
        E=clamp(0.50 * org + 0.50 * msg),
        V=clamp(1.00 * sup + 1.00 * cer),
        C=clamp(1.00 * org + 0.50 * sup + 1.00 * msg + 0.50 * cer),
    )
    delivery = AudienceState(
        E=clamp(0.50 * lang + 1.00 * vocal + 1.00 * gaze),
        V=clamp(0.50 * vocal + 0.50 * gaze + 0.50 * align),
        C=clamp(1.00 * lang + 1.00 * align),
    )
    common = AudienceState(
        E=0.45 * content.E + 0.55 * delivery.E,
        V=0.55 * content.V + 0.45 * delivery.V,
        C=0.50 * content.C + 0.50 * delivery.C,
    )
    return StateDeltaBreakdown(content=content, delivery=delivery, common=common)


def negative_change_sensitivity(setting: float) -> float:
    if setting == 0.25:
        return 1.20
    if setting == 0.50:
        return 1.00
    if setting == 0.75:
        return 0.80
    raise ValueError("state setting must be exactly 0.25, 0.50, or 0.75")


def update_audience_state(
    agent: AudienceRuntimeState,
    delta: AudienceState,
    topic_interest: float,
    prior_knowledge: float,
) -> tuple[AudienceState, StateSensitivity]:
    sensitivity = StateSensitivity(
        E=negative_change_sensitivity(topic_interest) if delta.E < 0 else 1.0,
        V=1.0,
        C=negative_change_sensitivity(prior_knowledge) if delta.C < 0 else 1.0,
    )
    previous = agent.state
    next_state = AudienceState(
        E=previous.E + sensitivity.E * delta.E,
        V=previous.V + sensitivity.V * delta.V,
        C=previous.C + sensitivity.C * delta.C,
    )
    return next_state, sensitivity
