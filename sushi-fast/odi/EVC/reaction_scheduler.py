"""Per-listener evaluation clocks over shared, immutable presentation evidence.

No LLM/STT calls run here. tick/publish contain no awaits: commits are atomic on
the server event loop even while the analysis request waits on its provider.
"""
from __future__ import annotations

import random
import copy
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, field, replace
from uuid import UUID

from pydantic import Field

from .behavior_engine import (build_candidate_set, commit_selection, select_behaviors,
    limit_synchronized_core_choice, limit_synchronized_action_choice,
    update_engagement_counters, action_clip_matches)
from .clip_pool import load_clip_pool
from .command_builder import build_unity_commands, commit_command_times
from .schema import (StrictModel, AudienceDecision, AudienceRuntimeState, AudienceState,
    SegmentContext, SpeechMetrics, UnityCommand)
from .state_engine import update_audience_state


class ReactionRequest(StrictModel):
    request_id: UUID
    client_time_s: float = Field(ge=0, allow_inf_nan=False)


class ReactionResponse(StrictModel):
    session_id: UUID
    request_id: UUID
    sequence: int
    audiences: list[AudienceDecision] = Field(default_factory=list)
    commands: list[UnityCommand] = Field(default_factory=list)


@dataclass(frozen=True)
class Evidence:
    step: int
    delta: AudienceState
    context: SegmentContext
    metrics: SpeechMetrics
    slide_text: str


@dataclass
class Listener:
    agent: AudienceRuntimeState
    timing_rng: random.Random
    choice_rng: random.Random
    interval: float
    max_hold: float
    next_at: float
    pending: deque = field(default_factory=deque)
    consumed_step: int = 0
    current_core: str | None = None
    core_state: AudienceState | None = None
    last_core_at: float = -1000
    action: str | None = None
    action_until: float = 0


class AudienceReactionScheduler:
    # A stalled poll must not release six overdue decisions in one frame.
    MIN_SEPARATION = 0.35

    def __init__(self, agents, seed, interest, knowledge):
        self.interest, self.knowledge = interest, knowledge
        self.catalog = load_clip_pool()
        self.listeners = {}
        order = list(range(len(agents)))
        random.Random(seed ^ 0x51A7).shuffle(order)
        for i, source in enumerate(agents):
            timing = random.Random(f"{seed}:evaluation:{source.agent_id}")
            self.listeners[source.agent_id] = Listener(
                agent=source.model_copy(deep=True), timing_rng=timing,
                choice_rng=random.Random(f"{seed}:reaction:{source.agent_id}"),
                interval=2.5 + 3 * (1 - source.profile.responsiveness) + timing.uniform(-.4, .4),
                max_hold=timing.uniform(9, 15),
                next_at=.35 + order[i] * .55 + timing.uniform(0, .2))
        self.last_publish_step = 0
        self.last_dispatch = -1000.0
        self.last_time = 0.0
        self.sequence = 0
        self.cache = OrderedDict()

    def publish(self, evidence):
        if evidence.step <= self.last_publish_step:
            return
        self.last_publish_step = evidence.step
        for listener in self.listeners.values():
            listener.pending.append(evidence)

    def tick(self, session_id, request):
        if request.request_id in self.cache:
            return self.cache[request.request_id]
        now = max(self.last_time, request.client_time_s)
        self.last_time = now
        decisions, commands = [], []
        due = sorted((l for l in self.listeners.values() if l.next_at <= now),
                     key=lambda l: l.next_at)
        if now - self.last_dispatch >= self.MIN_SEPARATION:
            for listener in due:
                if not listener.pending:
                    listener.next_at = now + listener.interval + listener.timing_rng.uniform(-.55, .55)
                    continue
                # A mapping/selection error must not consume the evidence or RNG
                # state. Share immutable evidence references in the backup.
                backup = {}
                for key, source in self.listeners.items():
                    snapshot = copy.copy(source)
                    snapshot.agent = source.agent.model_copy(deep=True)
                    snapshot.pending = deque(source.pending)
                    snapshot.timing_rng = copy.deepcopy(source.timing_rng)
                    snapshot.choice_rng = copy.deepcopy(source.choice_rng)
                    backup[key] = snapshot
                try:
                    listener.next_at = now + listener.interval + listener.timing_rng.uniform(-.55, .55)
                    decision, emitted = self._evaluate(listener, now)
                except Exception:
                    self.listeners = backup
                    raise
                decisions.append(decision)
                commands.extend(emitted)
                self.last_dispatch = now
                break
        self.sequence += 1
        response = ReactionResponse(session_id=session_id, request_id=request.request_id,
            sequence=self.sequence, audiences=decisions, commands=commands)
        self.cache[request.request_id] = response
        while len(self.cache) > 32:
            self.cache.popitem(last=False)
        return response

    def _evaluate(self, listener, now):
        agent = listener.agent
        previous = agent.state.model_copy()
        # Apply every unseen segment once, in order (clamping/sensitivity are not
        # distributive). Select only one reaction to the resulting recent state.
        while listener.pending:
            evidence = listener.pending.popleft()
            agent.state, sensitivity = update_audience_state(
                agent, evidence.delta, self.interest, self.knowledge)
            update_engagement_counters(agent)
            listener.consumed_step = evidence.step
        context = evidence.context.model_copy(update={"client_time_s": now})
        # A rear pair may interact during a pause after sustained disengagement;
        # this does not depend on a front-end forcing a nearby-interaction event.
        if agent.profile.row == "rear" and context.utterance_position == "silence_or_pause" and agent.consecutive_low_engagement >= 2:
            context.event_signals = context.event_signals.model_copy(update={
                "nearby_interaction": max(.5, context.event_signals.nearby_interaction)})
        candidates = build_candidate_set(agent=agent, context=context, catalog=self.catalog,
            speech_metrics=evidence.metrics, current_slide_text=evidence.slide_text,
            delta=evidence.delta, now_s=now)
        selection = select_behaviors(agent, candidates, listener.choice_rng)
        peers = [l for l in self.listeners.values() if l is not listener]
        core_counts = Counter(l.current_core for l in peers if l.current_core)
        action_counts = Counter(l.action for l in peers if l.action and l.action_until > now)
        selection = limit_synchronized_core_choice(selection, candidates, core_counts, rng=listener.choice_rng)
        selection = limit_synchronized_action_choice(selection, candidates, action_counts, listener.choice_rng)
        # Compare with the last displayed core, not the last evaluation: small
        # changes accumulate and can eventually justify a new reaction.
        distance = max(abs(getattr(agent.state, a) - getattr(listener.core_state, a))
                       for a in ("E", "V", "C")) if listener.core_state else 1
        if listener.current_core and distance < .12 and now - listener.last_core_at < listener.max_hold:
            selection = replace(selection, core=None, no_op_reason="state_change_below_threshold")
        if selection.core and selection.core.variation_id == listener.current_core:
            selection = replace(selection, core=None, no_op_reason="same_core_kept")

        # Paired conversation is the only deliberate synchronized action. The
        # partner must independently pass the same rear-seat/state/cooldown gates.
        partner = None
        if selection.action and selection.action.behavior_id == "ACT_08":
            partners = [l for l in peers if l.agent.profile.row == "rear"]
            clip = next(c for c in self.catalog.actions if c.variation_id == selection.action.variation_id)
            if agent.profile.row == "rear" and len(partners) == 1:
                possible = partners[0]
                if action_clip_matches(clip, possible.agent, context, candidates.event_signals,
                        possible.agent.previous_dominant_axis, candidates.direction, now):
                    partner = possible
            if partner is None:
                selection = replace(selection, action=None)

        commands = build_unity_commands(agent=agent, core=selection.core, action=selection.action,
            catalog=self.catalog, context=context, accepted_time_s=now)
        if partner:
            paired = build_unity_commands(agent=partner.agent, core=None, action=selection.action,
                catalog=self.catalog, context=context, accepted_time_s=now)
            sync = next(c.sync_group for c in commands if c.selected_behavior_id == "ACT_08")
            for command in paired:
                command.sync_group = sync
            commands.extend(paired)
            pair_selection = replace(selection, core=None)
            commit_selection(partner.agent, pair_selection, now)
            commit_command_times(partner.agent, paired)
            partner.action, partner.action_until = "ACT_08", now + max(c.duration for c in paired)
        commit_selection(agent, selection, now)
        commit_command_times(agent, [c for c in commands if c.agent_id == agent.agent_id])
        if selection.core:
            listener.current_core = selection.core.variation_id
            listener.core_state = agent.state.model_copy()
            listener.last_core_at = now
        if selection.action:
            listener.action = selection.action.behavior_id
            listener.action_until = now + max(c.duration for c in commands
                if c.agent_id == agent.agent_id and c.selected_behavior_id == listener.action)
        decision = AudienceDecision(agent_id=agent.agent_id, previous_state=previous,
            sensitivity=sensitivity, state=agent.state.model_copy(),
            dominant_axis=selection.dominant_axis, direction=selection.direction,
            core_behavior=selection.core, action_overlay=selection.action,
            no_op_reason=selection.no_op_reason)
        return decision, commands
