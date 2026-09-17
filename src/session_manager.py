"""Session accounting integrates the previous observed state over each valid interval."""
import logging
from dataclasses import dataclass
from src.attention_engine import State
from src.database import utc_now


@dataclass
class Stats:
    elapsed: float = 0
    focus: float = 0
    phone: float = 0
    pickups: int = 0
    warnings: int = 0
    longest_focus: float = 0
    focus_streak: float = 0


class SessionManager:
    def __init__(self, db, config):
        self.db, self.config = db, config
        self.id = None
        self.stats = Stats()
        self.mode = "stopped"
        self.previous = State.UNCERTAIN
        self.confidence = 0
        self.last = None

    def start(self, task, minutes, now):
        if self.id is not None:
            raise ValueError("Stop the current session first")
        if not task.strip() or not 0 < minutes <= 1440:
            raise ValueError("Enter a task and duration between 0 and 1440 minutes")
        self.task, self.planned = task.strip(), minutes * 60
        self.stats = Stats()
        self.id = self.db.execute("INSERT INTO sessions(task,started,planned_seconds) VALUES(?,?,?)",
                                  (self.task, utc_now(), self.planned)).lastrowid
        self.mode, self.last, self.previous = "running", now, State.UNCERTAIN

    def advance(self, now):
        if self.id is None:
            return
        dt = max(0, now - self.last)
        self.last = now
        if self.mode == "paused":
            return
        dt = min(dt, max(0, self.planned - self.stats.elapsed))
        self.stats.elapsed += dt
        state = State.BREAK if self.mode == "break" else self.previous
        if dt > self.config.max_frame_gap:
            state = State.UNCERTAIN
        if state == State.FOCUSED:
            self.stats.focus += dt
            self.stats.focus_streak += dt
            self.stats.longest_focus = max(self.stats.longest_focus, self.stats.focus_streak)
        else:
            self.stats.focus_streak = 0
        if state in (State.PHONE_USE, State.PHONE_GLANCE):
            self.stats.phone += dt
        if dt:
            self.db.execute("INSERT INTO attention_events(session_id,timestamp,state,confidence,duration) VALUES(?,?,?,?,?)",
                            (self.id, utc_now(), state, self.confidence, dt))
        self.persist()

    def update(self, attention, now):
        self.advance(now)
        if self.mode != "running":
            return
        phone_states = (State.PHONE_GLANCE, State.PHONE_USE)
        if attention.state in phone_states and self.previous not in phone_states:
            self.stats.pickups += 1
        if attention.state != self.previous:
            logging.info("Attention state: %s", attention.state)
        self.previous, self.confidence = attention.state, attention.confidence

    def set_mode(self, mode, now):
        self.advance(now)
        self.mode = mode
        self.previous = State.UNCERTAIN
        self.stats.focus_streak = 0

    def persist(self):
        s = self.stats
        self.db.execute("UPDATE sessions SET elapsed=?,focus=?,phone=?,pickups=?,warnings=?,longest_focus=? WHERE id=?",
                        (s.elapsed, s.focus, s.phone, s.pickups, s.warnings, s.longest_focus, self.id))

    def stop(self, now):
        if self.id is not None:
            self.advance(now)
            self.db.execute("UPDATE sessions SET ended=? WHERE id=?", (utc_now(), self.id))
            logging.info("Focus session completed")
        self.id, self.mode = None, "stopped"
