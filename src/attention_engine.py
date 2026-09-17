"""Elapsed-time smoothing; observation time must be monotonic, never wall time."""
from dataclasses import dataclass
from enum import StrEnum


class State(StrEnum):
    FOCUSED = "FOCUSED"
    PHONE_GLANCE = "PHONE_GLANCE"
    PHONE_USE = "PHONE_USE"
    AWAY = "AWAY"
    BREAK = "BREAK"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class Observation:
    phone: bool = False
    hand_near: bool = False
    person: bool = True
    confidence: float = 1.0
    reliable: bool = True


@dataclass
class Attention:
    state: State
    confidence: float
    continuous: float


class AttentionEngine:
    def __init__(self, config):
        self.config = config
        self.reset()

    def reset(self):
        self.started = self.last_positive = self.last_time = None

    def update(self, observation, now, on_break=False):
        if self.last_time is not None and now < self.last_time:
            raise ValueError("Observation timestamps must be monotonic")
        if self.last_time is not None and now - self.last_time > self.config.max_frame_gap:
            self.reset()
        self.last_time = now
        if on_break or not observation.reliable:
            self.started = self.last_positive = None
            return Attention(State.BREAK if on_break else State.UNCERTAIN, 0, 0)
        positive = observation.phone and observation.hand_near and observation.person
        if positive:
            if self.started is None:
                self.started = now
            self.last_positive = now
        elif self.last_positive is None or now - self.last_positive > self.config.dropout_seconds:
            self.started = self.last_positive = None
        if self.started is not None:
            duration = now - self.started
            state = State.UNCERTAIN if duration < self.config.smoothing_seconds else (
                State.PHONE_GLANCE if duration < self.config.glance_seconds else State.PHONE_USE)
            return Attention(state, min(1, max(0, observation.confidence if positive else 0.4)), duration)
        state = State.AWAY if not observation.person else (State.UNCERTAIN if observation.phone else State.FOCUSED)
        return Attention(state, min(1, max(0, observation.confidence)), 0)
