"""Per-listener evaluation clocks over shared, immutable presentation evidence.

No LLM/STT calls run here. tick/publish contain no awaits: commits are atomic on
the server event loop even while the analysis request waits on its provider.
"""
from __future__ import annotations

import random
import copy
import time
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, field, replace
from uuid import UUID

from pydantic import Field

from .behavior_engine import (build_candidate_set, commit_selection, select_behaviors,
    limit_synchronized_core_choice, limit_synchronized_action_choice,
    update_engagement_counters, action_clip_matches)
from .clip_pool import load_clip_pool
from .audience_config import bind_audience_catalog
from .command_builder import build_unity_commands, commit_command_times
from .schema import (StrictModel, AudienceDecision, AudienceRuntimeState, AudienceState,
    SegmentContext, SpeechMetrics, UnityCommand)
from .state_engine import update_audience_state
from .playback_policy import PlaybackPolicy
from .session_store import SessionCapacityError


class ReactionRequest(StrictModel):
    request_id: UUID
    client_time_s: float = Field(ge=0, allow_inf_nan=False)


class ReactionResponse(StrictModel):
    session_id: UUID
    request_id: UUID
    sequence: int
    audiences: list[AudienceDecision] = Field(default_factory=list)
    commands: list[UnityCommand] = Field(default_factory=list)
    # Exact analytical steps consumed by the listener that reacted in this tick.
    source_steps: list[int] = Field(default_factory=list)


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

    def __init__(self, agents, seed, interest, knowledge, *, policy=None, monotonic_clock=time.monotonic):
        self.policy = policy or PlaybackPolicy()
        self.monotonic_clock = monotonic_clock
        self.interest, self.knowledge = interest, knowledge
        self.catalog = bind_audience_catalog(load_clip_pool(), agents)
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
        self.last_poll_monotonic = None
        self.sequence = 0
        self.cache = OrderedDict()
        self.playback_drops = deque(maxlen=128)
        self.dropped_playback_count = 0
        self.last_tick_metadata = {}

    def ensure_evidence_capacity(self):
        if any(len(listener.pending) >= self.policy.max_pending_evidence for listener in self.listeners.values()):
            raise SessionCapacityError("reaction evidence backlog reached capacity; poll before retrying update")

    def publish(self, evidence):
        if evidence.step <= self.last_publish_step:
            return
        self.ensure_evidence_capacity()
        self.last_publish_step = evidence.step
        for listener in self.listeners.values():
            listener.pending.append(evidence)

    def tick(self, session_id, request):
        if request.request_id in self.cache:
            return self.cache[request.request_id]
        received = self.monotonic_clock()
        now = self.policy.poll_time(request.client_time_s, self.last_time, self.last_poll_monotonic, received)
        paused = self.last_poll_monotonic is not None and now == self.last_time
        decisions, commands, source_steps = [], [], []
        due = sorted((l for l in self.listeners.values() if l.next_at <= now),
                     key=lambda l: l.next_at)
        backup = self._snapshot()
        old_dispatch, old_drops = self.last_dispatch, list(self.playback_drops)
        old_drop_count = self.dropped_playback_count
        waits = {}
        assessments = []
        batch_size = min(self.policy.max_batch, max(1, (len(self.listeners) + 5) // 6))
        try:
            if not paused and now - self.last_dispatch >= self.MIN_SEPARATION:
                for source in due:
                    listener = self.listeners[source.agent.agent_id]
                    if not listener.pending:
                        listener.next_at = now + listener.interval + listener.timing_rng.uniform(-.55, .55)
                        continue
                    candidate_backup = self._snapshot()
                    candidate_drops = list(self.playback_drops)
                    candidate_drop_count = self.dropped_playback_count
                    consumed_now = [item.step for item in listener.pending]
                    latest = listener.pending[-1]
                    _, event_age, reason, expired = self.policy.assess(latest.context, now)
                    wait = max(0., now - listener.next_at)
                    listener.next_at = now + listener.interval + listener.timing_rng.uniform(-.55, .55)
                    decision, emitted = self._evaluate(listener, now)
                    if len(commands) + len(emitted) > self.policy.command_budget:
                        # Roll back the whole choice (including a paired actor),
                        # never truncate decomposed layers or consume its delta.
                        self.listeners = candidate_backup
                        self.playback_drops = deque(candidate_drops, maxlen=128)
                        self.dropped_playback_count = candidate_drop_count
                        break
                    decisions.append(decision)
                    commands.extend(emitted)
                    source_steps.extend(consumed_now)
                    waits[decision.agent_id] = wait
                    assessments.append({"agent_id": decision.agent_id, "source_step": latest.step,
                        "event_age_s": event_age, "drop_reason": "stale_playback" if expired else reason})
                    self.last_dispatch = now
                    if len(decisions) >= batch_size:
                        break
        except Exception:
            self.listeners = backup
            self.last_dispatch = old_dispatch
            self.playback_drops = deque(old_drops, maxlen=128)
            self.dropped_playback_count = old_drop_count
            raise
        self.last_time, self.last_poll_monotonic = now, received
        self.sequence += 1
        response = ReactionResponse(session_id=session_id, request_id=request.request_id,
            sequence=self.sequence, audiences=decisions, commands=commands,
            source_steps=list(dict.fromkeys(source_steps)))
        self.cache[request.request_id] = response
        while len(self.cache) > 32:
            self.cache.popitem(last=False)
        new_drops = self.dropped_playback_count - old_drop_count
        self.last_tick_metadata = {
            "clock_source": "client_poll_unverified", "unity_clock_s": None,
            "poll_clock_s": now, "paused_clock": paused, "due_count": len(due),
            "actor_wait_s": waits, "command_count": len(commands), "batch_limit": batch_size,
            "pending_evidence_counts": {key: len(l.pending) for key, l in self.listeners.items()},
            "source_steps": list(dict.fromkeys(source_steps)), "playback_assessments": assessments,
            "playback_drops": list(self.playback_drops)[-new_drops:] if new_drops else [],
        }
        return response

    def _snapshot(self):
        result = {}
        for key, source in self.listeners.items():
            snapshot = copy.copy(source)
            snapshot.agent = source.agent.model_copy(deep=True)
            snapshot.pending = deque(source.pending)
            snapshot.timing_rng = copy.deepcopy(source.timing_rng)
            snapshot.choice_rng = copy.deepcopy(source.choice_rng)
            result[key] = snapshot
        return result

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
        context, age, drop_reason, playback_expired = self.policy.assess(evidence.context, now)
        if drop_reason or playback_expired:
            self.dropped_playback_count += 1
            self.playback_drops.append({"agent_id": agent.agent_id, "source_step": evidence.step,
                "event_age_s": age, "reason": "stale_playback" if playback_expired else drop_reason})
        # A rear pair may interact during a pause after sustained disengagement;
        # this does not depend on a front-end forcing a nearby-interaction event.
        if agent.profile.row == "rear" and context.utterance_position == "silence_or_pause" and agent.consecutive_low_engagement >= 2:
            context.event_signals = context.event_signals.model_copy(update={
                "nearby_interaction": max(.5, context.event_signals.nearby_interaction)})
        candidates = build_candidate_set(agent=agent, context=context, catalog=self.catalog,
            speech_metrics=evidence.metrics, current_slide_text=evidence.slide_text,
            delta=evidence.delta, now_s=now)
        if drop_reason:
            # Derived signals from historical metrics must not recreate expired actions.
            # An ahead timestamp has unknown age, not proof of expired state:
            # retain only ACT03 derived from the current disengagement counters.
            actions = tuple(c for c in candidates.actions if c.behavior_id == "ACT_03") if drop_reason == "evidence_clock_ahead" else ()
            candidates = replace(candidates, actions=actions)
        selection = select_behaviors(agent, candidates, listener.choice_rng)
        if playback_expired:
            # Still validate selection/mapping admission so an implementation
            # failure rolls back consumption rather than looking like expiry.
            return AudienceDecision(agent_id=agent.agent_id, previous_state=previous,
                sensitivity=sensitivity, state=agent.state.model_copy(), dominant_axis=selection.dominant_axis,
                direction=selection.direction, core_behavior=None, action_overlay=None, no_op_reason="stale_playback"), []
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
            rear = sorted((l for l in self.listeners.values() if l.agent.profile.row == "rear"),
                          key=lambda l: l.agent.agent_id)
            clip = next(c for c in self.catalog.actions if c.variation_id == selection.action.variation_id)
            # Adjacent registry pairs (0,1), (2,3), ...; an odd tail stays unpaired.
            rear_index = next((i for i, l in enumerate(rear) if l is listener), None)
            if rear_index is not None and (rear_index ^ 1) < len(rear):
                possible = rear[rear_index ^ 1]
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
