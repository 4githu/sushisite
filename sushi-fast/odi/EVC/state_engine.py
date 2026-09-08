from __future__ import annotations

import hashlib
import math
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
    interests = distribute_population_trait(options.topic_interest, seed, "topic_interest")
    knowledge = distribute_population_trait(options.prior_knowledge, seed, "prior_knowledge")
    audiences: list[AudienceRuntimeState] = []

    for index, (agent_id, row, seat) in enumerate(AUDIENCE_LAYOUT):
        rng = agent_rngs[agent_id]
        # Preserve the independent behavioral-trait RNG sequence for an existing seed.
        rng.uniform(-0.05, 0.05)
        rng.uniform(-0.05, 0.05)
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
            topic_interest=interests[index],
            prior_knowledge=knowledge[index],
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
                state=AudienceState(
                    E=(interests[index] - 0.50) * 2.0,
                    V=0.0,
                    C=(knowledge[index] - 0.50) * 2.0,
                ),
            )
        )

    return audiences


def distribute_population_trait(mean: float, seed: int, trait: str) -> list[float]:
    """Six bounded, distinct traits whose mean is exactly the web setting (within FP precision).

    Three positive/negative pairs avoid shifting the mean through clipping. Shuffle
    interest and knowledge independently so they are not tied to gender or seat order.
    The maximum spread is a tuning parameter, not an extra random EVC perturbation.
    """
    if not math.isfinite(mean) or not 0.0 <= mean <= 1.0:
        raise ValueError("population mean must be finite and within [0, 1]")
    rng = random.Random(derive_agent_seed(seed, "population:" + trait))
    spread = min(0.20, mean, 1.0 - mean)
    values = []
    for low, high in ((0.25, 0.45), (0.50, 0.70), (0.75, 0.95)):
        offset = spread * rng.uniform(low, high)
        values.extend((mean - offset, mean + offset))
    rng.shuffle(values)
    return values



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


def individual_negative_sensitivity(value: float) -> float:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("individual state trait must be finite and within [0, 1]")
    # Continuous extension of the existing anchors: .25->1.2, .50->1, .75->.8.
    return max(0.6, min(1.4, 1.4 - 0.8 * value))


def update_audience_state(
    agent: AudienceRuntimeState,
    delta: AudienceState,
    topic_interest: float,
    prior_knowledge: float,
) -> tuple[AudienceState, StateSensitivity]:
    interest = agent.profile.topic_interest
    knowledge = agent.profile.prior_knowledge
    sensitivity = StateSensitivity(
        E=(individual_negative_sensitivity(interest) if interest is not None
           else negative_change_sensitivity(topic_interest)) if delta.E < 0 else 1.0,
        V=1.0,
        C=(individual_negative_sensitivity(knowledge) if knowledge is not None
           else negative_change_sensitivity(prior_knowledge)) if delta.C < 0 else 1.0,
    )
    previous = agent.state
    return AudienceState(
        E=previous.E + sensitivity.E * delta.E,
        V=previous.V + delta.V,
        C=previous.C + sensitivity.C * delta.C,
    ), sensitivity
