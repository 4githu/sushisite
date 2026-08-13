from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .schema import (
    ActionClipSpec,
    AudienceGroup,
    AudienceRuntimeState,
    AudienceState,
    BehaviorChoice,
    BehaviorHistoryEntry,
    ClipPoolCatalog,
    CoreClipSpec,
    Direction,
    DominantAxis,
    EventSignals,
    SegmentContext,
    SpeechMetrics,
    StateCondition,
    StateLevel,
)


TIE_THRESHOLD = 0.10


@dataclass(frozen=True)
class CandidateSet:
    dominant_axis: DominantAxis | None
    direction: Direction | None
    base_group: AudienceGroup
    event_signals: EventSignals
    core: tuple[CoreClipSpec, ...]
    actions: tuple[ActionClipSpec, ...]
    used_baseline_fallback: bool = False


@dataclass(frozen=True)
class SelectionResult:
    dominant_axis: DominantAxis | None
    direction: Direction | None
    core: BehaviorChoice | None
    action: BehaviorChoice | None
    no_op_reason: str | None
    diagnostics: dict[str, object]


def classify_level(value: float) -> StateLevel:
    if value <= -0.34:
        return "low"
    if value >= 0.34:
        return "high"
    return "mid"


def choose_dominant_axis(
    state: AudienceState,
    previous: DominantAxis | None = None,
) -> tuple[DominantAxis | None, Direction | None]:
    levels = {axis: classify_level(getattr(state, axis)) for axis in ("E", "V", "C")}
    if all(level == "mid" for level in levels.values()):
        return None, None

    magnitudes = {axis: abs(getattr(state, axis)) for axis in ("E", "V", "C")}
    ranked = sorted(magnitudes.values(), reverse=True)
    max_magnitude = ranked[0]
    if max_magnitude - ranked[1] > TIE_THRESHOLD:
        axis = max(magnitudes, key=magnitudes.get)
        return axis, "positive" if getattr(state, axis) > 0 else "negative"

    tied = {
        axis for axis, magnitude in magnitudes.items() if max_magnitude - magnitude <= TIE_THRESHOLD
    }
    for axis in ("C", "V", "E"):
        if axis in tied and getattr(state, axis) <= -0.34:
            return axis, "negative"
    if previous in tied:
        return previous, "positive" if getattr(state, previous) > 0 else "negative"
    for axis in ("E", "C", "V"):
        if axis in tied:
            return axis, "positive" if getattr(state, axis) > 0 else "negative"
    raise AssertionError("dominant axis tie set cannot be empty")


def base_group_for_axis(axis: DominantAxis | None) -> AudienceGroup:
    if axis is None:
        return "Baseline Listening"
    return {
        "E": "Attentive Listening",
        "V": "Evaluative Monitoring",
        "C": "Comprehension Tracking",
    }[axis]


def state_condition_matches(
    condition: StateCondition,
    state: AudienceState,
    dominant_axis: DominantAxis | None,
    direction: Direction | None,
) -> bool:
    for axis in ("E", "V", "C"):
        allowed = getattr(condition, axis)
        if allowed is not None and classify_level(getattr(state, axis)) not in allowed:
            return False
    if condition.dominant_axis is not None and condition.dominant_axis != dominant_axis:
        return False
    if condition.direction is not None and condition.direction != direction:
        return False
    return True


def core_clip_matches(
    clip: CoreClipSpec,
    agent: AudienceRuntimeState,
    context: SegmentContext,
    dominant_axis: DominantAxis | None,
    direction: Direction | None,
    now_s: float,
) -> bool:
    if context.utterance_position not in clip.utterance_positions:
        return False
    if clip.requires_slide_reference and not context.slide_reference:
        return False
    if not cooldown_is_ready(agent, clip.variation_id, clip.cooldown_s, now_s):
        return False
    return any(
        state_condition_matches(condition, agent.state, dominant_axis, direction)
        for condition in clip.trigger_conditions
    )


def action_clip_matches(
    clip: ActionClipSpec,
    agent: AudienceRuntimeState,
    context: SegmentContext,
    events: EventSignals,
    dominant_axis: DominantAxis | None,
    direction: Direction | None,
    now_s: float,
) -> bool:
    if context.utterance_position not in clip.utterance_positions:
        return False
    if clip.requires_slide_reference and not context.slide_reference:
        return False
    if max(getattr(events, event_name) for event_name in clip.event_triggers) <= 0.0:
        return False
    if clip.state_gates and not any(
        state_condition_matches(condition, agent.state, dominant_axis, direction)
        for condition in clip.state_gates
    ):
        return False
    gate = clip.scene_gate
    if gate.requires_laptop and not agent.profile.has_laptop:
        return False
    if gate.allowed_agents is not None and agent.agent_id not in gate.allowed_agents:
        return False
    if gate.allowed_rows is not None and agent.profile.row not in gate.allowed_rows:
        return False
    return cooldown_is_ready(agent, clip.variation_id, clip.cooldown_s, now_s)


def cooldown_is_ready(
    agent: AudienceRuntimeState,
    variation_id: str,
    cooldown_s: float,
    now_s: float,
) -> bool:
    last_used = agent.cooldowns.get(variation_id)
    return last_used is None or now_s - last_used >= cooldown_s


def derive_event_signals(
    *,
    agent: AudienceRuntimeState,
    context: SegmentContext,
    speech_metrics: SpeechMetrics,
    current_slide_text: str,
    delta: AudienceState,
    now_s: float,
) -> EventSignals:
    derived = {
        "information_dense": 1.0
        if speech_metrics.word_count >= 45 or len(current_slide_text.strip()) >= 700
        else 0.0,
        "slide_reference": 1.0 if context.slide_reference else 0.0,
        "repeated_disengagement": 1.0
        if agent.consecutive_low_engagement >= 2
        else 0.0,
        "low_arousal": 1.0 if agent.consecutive_low_arousal >= 3 else 0.0,
        "long_static_posture": 1.0 if now_s - agent.last_body_command_time >= 12.0 else 0.0,
        "tension": 1.0 if classify_level(agent.state.V) == "low" and delta.V <= -0.15 else 0.0,
        "nearby_interaction": 0.0,
    }
    client = context.event_signals.model_dump()
    return EventSignals(**{name: max(client[name], strength) for name, strength in derived.items()})


def build_candidate_set(
    *,
    agent: AudienceRuntimeState,
    context: SegmentContext,
    catalog: ClipPoolCatalog,
    speech_metrics: SpeechMetrics,
    current_slide_text: str,
    delta: AudienceState,
    now_s: float,
) -> CandidateSet:
    dominant_axis, direction = choose_dominant_axis(
        agent.state,
        agent.previous_dominant_axis,
    )
    events = derive_event_signals(
        agent=agent,
        context=context,
        speech_metrics=speech_metrics,
        current_slide_text=current_slide_text,
        delta=delta,
        now_s=now_s,
    )
    core = tuple(
        clip
        for clip in catalog.core
        if core_clip_matches(clip, agent, context, dominant_axis, direction, now_s)
    )
    used_fallback = False
    if not core:
        core = tuple(
            clip
            for clip in catalog.core
            if clip.parent_group == "Baseline Listening"
            and context.utterance_position in clip.utterance_positions
            and (not clip.requires_slide_reference or context.slide_reference)
            and cooldown_is_ready(agent, clip.variation_id, clip.cooldown_s, now_s)
        )
        used_fallback = bool(core)
    actions = tuple(
        clip
        for clip in catalog.actions
        if action_clip_matches(
            clip,
            agent,
            context,
            events,
            dominant_axis,
            direction,
            now_s,
        )
    )
    return CandidateSet(
        dominant_axis=dominant_axis,
        direction=direction,
        base_group=base_group_for_axis(dominant_axis),
        event_signals=events,
        core=core,
        actions=actions,
        used_baseline_fallback=used_fallback,
    )


def level_affinity(level: StateLevel, value: float) -> float:
    if level == "low":
        return max(0.0, min(1.0, (-value - 0.33) / 0.67))
    if level == "high":
        return max(0.0, min(1.0, (value - 0.33) / 0.67))
    return 1.0 - max(0.0, min(1.0, (abs(value) - 0.33) / 0.67))


def condition_state_fit(condition: StateCondition, state: AudienceState) -> float:
    affinities: list[float] = []
    for axis in ("E", "V", "C"):
        allowed = getattr(condition, axis)
        if allowed is not None:
            affinities.append(max(level_affinity(level, getattr(state, axis)) for level in allowed))
    return sum(affinities) / len(affinities) if affinities else 0.5


def channel_preference(agent: AudienceRuntimeState, channels: set[str]) -> float:
    weights = {
        "Face": agent.profile.channel_preference.face,
        "Body": agent.profile.channel_preference.body,
        "GazeHead": agent.profile.channel_preference.gaze_head,
    }
    return sum(weights[channel] for channel in channels) / len(channels)


def preference_score(
    agent: AudienceRuntimeState,
    expressivity_target: float,
    *,
    critical: bool,
) -> float:
    expressivity_fit = 1.0 - abs(agent.profile.expressivity - expressivity_target)
    score = 0.50 * agent.profile.responsiveness + 0.50 * expressivity_fit
    if critical and agent.state.V <= 0.33:
        score += 0.25 * (2.0 * agent.profile.critical_bias - 1.0)
    return max(0.0, min(1.0, score))


def history_score(agent: AudienceRuntimeState, clip: CoreClipSpec) -> float:
    if not agent.core_history:
        return 0.50
    previous = agent.core_history[-1]
    if previous.variation_id == clip.variation_id:
        return 0.0
    if previous.behavior_id.split("_")[0] == clip.behavior_id.split("_")[0]:
        return 0.75
    return 0.50


def repetition_score(history: list[BehaviorHistoryEntry], variation_id: str) -> float:
    count = sum(1 for entry in history[-5:] if entry.variation_id == variation_id)
    return min(count / 3.0, 1.0)


def score_core_candidate(
    agent: AudienceRuntimeState,
    clip: CoreClipSpec,
    dominant_axis: DominantAxis | None,
    direction: Direction | None,
) -> tuple[float, dict[str, float]]:
    matching = [
        condition
        for condition in clip.trigger_conditions
        if state_condition_matches(condition, agent.state, dominant_axis, direction)
    ]
    # A baseline clip can be injected as the last-resort candidate even when its
    # neutral-state trigger does not match the current state.  Treat that explicit
    # safety fallback as neutral instead of failing the whole update.
    state_fit = (
        max(condition_state_fit(condition, agent.state) for condition in matching)
        if matching
        else 0.50
    )
    preference = preference_score(
        agent,
        clip.expressivity_target,
        critical=clip.critical,
    )
    channel = channel_preference(agent, clip.channels)
    history = history_score(agent, clip)
    repetition = repetition_score(agent.core_history, clip.variation_id)
    score = (
        2.00 * state_fit
        + 1.00 * preference
        + 0.75 * channel
        + 0.50 * history
        - 1.25 * repetition
    )
    return score, {
        "state_fit": state_fit,
        "preference": preference,
        "channel_preference": channel,
        "history": history,
        "repetition": repetition,
        "score": score,
    }


def score_action_candidate(
    agent: AudienceRuntimeState,
    clip: ActionClipSpec,
    candidates: CandidateSet,
) -> tuple[float, float, dict[str, float]]:
    matching = [
        condition
        for condition in clip.state_gates
        if state_condition_matches(
            condition,
            agent.state,
            candidates.dominant_axis,
            candidates.direction,
        )
    ]
    state_fit = (
        max(condition_state_fit(condition, agent.state) for condition in matching)
        if matching
        else 0.5
    )
    event_strength = max(
        getattr(candidates.event_signals, event_name) for event_name in clip.event_triggers
    )
    channel = channel_preference(agent, clip.channels)
    repetition = repetition_score(agent.action_history, clip.variation_id)
    score = (
        2.00 * state_fit
        + 1.50 * event_strength
        + 0.75 * channel
        + 0.50 * agent.profile.responsiveness
        - 1.00 * repetition
    )
    return score, event_strength, {
        "state_fit": state_fit,
        "event_strength": event_strength,
        "channel_preference": channel,
        "responsiveness": agent.profile.responsiveness,
        "repetition": repetition,
        "score": score,
    }


def softmax(scores: list[float], temperature: float = 1.0) -> list[float]:
    if not scores:
        return []
    if temperature <= 0 or not math.isfinite(temperature):
        raise ValueError("softmax temperature must be finite and positive")
    if not all(math.isfinite(score) for score in scores):
        raise ValueError("softmax scores must be finite")
    maximum = max(scores)
    exponentials = [math.exp((score - maximum) / temperature) for score in scores]
    total = sum(exponentials)
    return [value / total for value in exponentials]


def sample_categorical(probabilities: list[float], rng: random.Random) -> int:
    if not probabilities or not math.isclose(sum(probabilities), 1.0, abs_tol=1e-9):
        raise ValueError("categorical probabilities must be non-empty and sum to 1")
    threshold = rng.random()
    cumulative = 0.0
    for index, probability in enumerate(probabilities):
        cumulative += probability
        if threshold < cumulative:
            return index
    return len(probabilities) - 1


def select_behaviors(
    agent: AudienceRuntimeState,
    candidates: CandidateSet,
    rng: random.Random,
) -> SelectionResult:
    diagnostics: dict[str, object] = {"core": {}, "actions": {}}
    core_choice: BehaviorChoice | None = None
    action_choice: BehaviorChoice | None = None
    no_op_reason: str | None = None

    if candidates.core:
        core_scores: list[float] = []
        for clip in candidates.core:
            score, parts = score_core_candidate(
                agent,
                clip,
                candidates.dominant_axis,
                candidates.direction,
            )
            core_scores.append(score)
            diagnostics["core"][clip.variation_id] = parts
        probabilities = softmax(core_scores)
        for clip, probability in zip(candidates.core, probabilities):
            diagnostics["core"][clip.variation_id]["probability"] = probability
        selected_index = sample_categorical(probabilities, rng)
        selected_clip = candidates.core[selected_index]
        selected_probability = probabilities[selected_index]
        if selected_clip.motion_class == "transient":
            emit_probability = 0.35 + 0.65 * agent.profile.responsiveness
            diagnostics["transient_emit_probability"] = emit_probability
            if rng.random() >= emit_probability:
                stable = [
                    (clip, probability)
                    for clip, probability in zip(candidates.core, probabilities)
                    if clip.motion_class == "stable"
                ]
                if stable:
                    selected_clip, selected_probability = max(stable, key=lambda item: item[1])
                else:
                    selected_clip = None
                    no_op_reason = "transient_gate_rejected"
        if selected_clip is not None:
            core_choice = BehaviorChoice(
                behavior_id=selected_clip.behavior_id,
                variation_id=selected_clip.variation_id,
                probability=selected_probability,
            )
    else:
        no_op_reason = "no_core_candidate"

    if candidates.actions:
        action_scores: list[float] = []
        event_strengths: list[float] = []
        for clip in candidates.actions:
            score, event_strength, parts = score_action_candidate(agent, clip, candidates)
            action_scores.append(score)
            event_strengths.append(event_strength)
            diagnostics["actions"][clip.variation_id] = parts
        probabilities = softmax(action_scores)
        for clip, probability in zip(candidates.actions, probabilities):
            diagnostics["actions"][clip.variation_id]["probability"] = probability
        selected_index = sample_categorical(probabilities, rng)
        selected_clip = candidates.actions[selected_index]
        event_strength = event_strengths[selected_index]
        insert_probability = min(
            0.85,
            max(
                0.0,
                0.15 + 0.55 * agent.profile.responsiveness + 0.20 * event_strength,
            ),
        )
        diagnostics["action_insert_probability"] = insert_probability
        if rng.random() < insert_probability:
            action_choice = BehaviorChoice(
                behavior_id=selected_clip.behavior_id,
                variation_id=selected_clip.variation_id,
                probability=probabilities[selected_index],
            )

    return SelectionResult(
        dominant_axis=candidates.dominant_axis,
        direction=candidates.direction,
        core=core_choice,
        action=action_choice,
        no_op_reason=no_op_reason,
        diagnostics=diagnostics,
    )


def commit_selection(
    agent: AudienceRuntimeState,
    selection: SelectionResult,
    now_s: float,
) -> None:
    agent.previous_dominant_axis = selection.dominant_axis
    for choice, history in (
        (selection.core, agent.core_history),
        (selection.action, agent.action_history),
    ):
        if choice is None:
            continue
        entry = BehaviorHistoryEntry(
            behavior_id=choice.behavior_id,
            variation_id=choice.variation_id,
            start_time=now_s,
        )
        history.append(entry)
        del history[:-8]
        agent.cooldowns[choice.variation_id] = now_s


def update_engagement_counters(agent: AudienceRuntimeState) -> None:
    if classify_level(agent.state.E) == "low":
        agent.consecutive_low_engagement += 1
    else:
        agent.consecutive_low_engagement = 0
    if agent.state.E <= -0.60:
        agent.consecutive_low_arousal += 1
    else:
        agent.consecutive_low_arousal = 0
    BehaviorChoice,
    BehaviorHistoryEntry,
