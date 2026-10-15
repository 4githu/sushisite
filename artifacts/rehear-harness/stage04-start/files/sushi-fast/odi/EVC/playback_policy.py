"""Internal server observations and poll-domain policy, never a Unity clock estimate."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .schema import EventSignals, SegmentContext


class PlaybackClockError(ValueError):
    """Clock discontinuity requires the client to resume its clock or restart."""


@dataclass(frozen=True)
class PlaybackPolicy:
    slide_ttl_s: float = 6.0
    pause_ttl_s: float = 2.0
    boundary_ttl_s: float = 2.0
    signal_ttl_s: float = 6.0
    max_playback_age_s: float = 15.0
    forward_slack_s: float = 30.0
    command_budget: int = 24
    max_batch: int = 4
    max_pending_evidence: int = 64

    def __post_init__(self):
        for name in ("slide_ttl_s", "pause_ttl_s", "boundary_ttl_s", "signal_ttl_s",
                     "max_playback_age_s", "forward_slack_s"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        for name, minimum in (("command_budget", 9), ("max_batch", 1), ("max_pending_evidence", 1)):
            if type(getattr(self, name)) is not int or getattr(self, name) < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")

    def poll_time(self, requested, last, last_monotonic, received_monotonic):
        if last_monotonic is None:
            return requested  # First observation has no epoch/offset reference.
        if requested < last - .25:
            raise PlaybackClockError("client_time_s regressed; resume the previous presentation clock or start a new session")
        elapsed = max(0., received_monotonic - last_monotonic)
        if requested - last > elapsed + self.forward_slack_s:
            raise PlaybackClockError("client_time_s jumped forward beyond observed elapsed time; clock was not advanced")
        return max(last, requested)  # Retain the existing .25s jitter tolerance.

    def assess(self, context: SegmentContext, poll_time: float):
        age = poll_time - context.client_time_s
        ttl = {"slide_transition": self.slide_ttl_s, "silence_or_pause": self.pause_ttl_s,
               "utterance_boundary": self.boundary_ttl_s}.get(context.utterance_position, self.signal_ttl_s)
        reason = "evidence_clock_ahead" if age < -.25 else "event_expired" if age > ttl else None
        playback_expired = age > self.max_playback_age_s
        current = context.model_copy(deep=True)
        current.client_time_s = poll_time
        if reason:
            current.utterance_position = "during_speech"
            current.slide_reference = False
            current.event_signals = EventSignals()
        return current, (age if age >= 0 else None), reason, playback_expired


@dataclass
class TimingTrace:
    received_monotonic: float
    evidence_client_time_s: float
    lock_acquired_monotonic: float = 0.
    stt_finished_monotonic: float = 0.
    evaluation_finished_monotonic: float = 0.
    commit_finished_monotonic: float = 0.
    response_ready_monotonic: float = 0.
    playback_clock_source: str = "unobserved"
    observed_poll_clock_s: float | None = None
    evidence_age_s: float | None = None
    unity_clock_s: None = None

    @property
    def processing_s(self):
        return self.response_ready_monotonic - self.received_monotonic

    @property
    def stt_s(self):
        return self.stt_finished_monotonic - self.lock_acquired_monotonic

    @property
    def evaluation_s(self):
        return self.evaluation_finished_monotonic - self.stt_finished_monotonic

    def metadata(self):
        return {**asdict(self), "processing_s": self.processing_s, "stt_s": self.stt_s,
                "evaluation_s": self.evaluation_s,
                "lock_wait_s": self.lock_acquired_monotonic - self.received_monotonic,
                "response_is_wire_send_time": False}
