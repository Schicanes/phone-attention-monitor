import logging
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from src.ai_agent import Decision, RuleBasedAgent
from src.attention_engine import State
from src.config import DATA
from src.database import utc_now
from src.email_service import EmailService
from src.screenshot_service import capture


def output_warning(config, decision):
    if config.alarm:
        try:
            import winsound
            for _ in range(decision.repetitions):
                winsound.Beep(1100, 450)
                time.sleep(0.15)
        except ImportError:
            print("\a", end="", flush=True)
    if config.voice:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(decision.message)
            engine.runAndWait()
            engine.stop()
        except Exception:
            logging.warning("Offline speech unavailable; visual warning remains active")


class InterventionManager:
    def __init__(self, db, config, output=output_warning, email=None):
        self.db, self.config, self.output = db, config, output
        self.email = email or EmailService()
        self.agent = RuleBasedAgent()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.audio_future = None
        self.last_warning = float("-inf")
        self.pending = []
        self.notice = ""

    def reset_session(self):
        self.last_warning = float("-inf")
        self.pending.clear()

    def poll(self):
        if self.future and self.future.done():
            session_id, future = self.email_session, self.future
            self.future = None
            try:
                future.result()
                status = "sent"
                self.notice = "Accountability email sent"
                logging.info("Parent email sent")
            except Exception:
                status = "failed"
                self.notice = "Email failed. Check SMTP settings and connectivity."
                logging.warning("Accountability email failed (credentials omitted)")
            self.db.execute("INSERT INTO email_events(session_id,timestamp,status) VALUES(?,?,?)",
                            (session_id, utc_now(), status))

    def tick(self, session, attention, now, frame=None, allow_email=True):
        self.poll()
        if session.mode != "running":
            self.pending.clear()
            return
        if attention.state == State.FOCUSED:
            for intervention_id, started in self.pending:
                self.db.execute("UPDATE interventions SET response_time=? WHERE id=?", (now-started, intervention_id))
                self.agent.observe_outcome(now-started)
            self.pending.clear()
        if attention.state in (State.BREAK, State.AWAY, State.UNCERTAIN):
            self.pending.clear()  # Unknown outcomes are never labeled successful responses.
        if (attention.state != State.PHONE_USE or attention.continuous <= self.config.phone_threshold
                or now - self.last_warning < self.config.warning_cooldown):
            return
        if self.audio_future and not self.audio_future.done():
            return
        history = self.db.rows("SELECT AVG(response_time) AS value FROM interventions WHERE type='voice'")[0]["value"]
        context = self.agent.observe({"warnings": session.stats.warnings, "phone_seconds": attention.continuous,
                                      "average_response_to_voice": history})
        decision = self.agent.decide(context) if self.config.agent_enabled else Decision("Please return to your task.")
        self.notice = decision.message
        self.last_warning = now
        session.stats.warnings += 1
        kind = "alarm+voice" if self.config.alarm and self.config.voice else (
            "alarm" if self.config.alarm else "voice" if self.config.voice else "notification")
        intervention_id = self.db.execute(
            "INSERT INTO interventions(session_id,timestamp,type,phone_duration) VALUES(?,?,?,?)",
            (session.id, utc_now(), kind, attention.continuous)).lastrowid
        self.pending.append((intervention_id, now))
        session.persist()
        logging.info("Warning triggered: %s", kind)
        config = deepcopy(self.config)
        self.agent.act(decision, lambda d: self._submit_audio(config, d))
        if allow_email and frame is not None and config.parent_mode and self.future is None:
            rows = self.db.rows("SELECT timestamp FROM email_events ORDER BY id DESC LIMIT 1")
            since = (datetime.now(timezone.utc) - datetime.fromisoformat(rows[0]["timestamp"])).total_seconds() if rows else float("inf")
            if since >= config.email_cooldown and self.email.configured():
                try:
                    photo = capture(frame, config)
                except Exception:
                    self.notice = "Photo could not be encoded. No email was sent."
                    logging.warning("Accountability photo encoding failed")
                    return
                logging.info("Accountability photo captured")
                self.db.execute("INSERT INTO email_events(session_id,timestamp,status) VALUES(?,?,?)",
                                (session.id, utc_now(), "attempt"))
                self.email_session = session.id
                self.future = self.executor.submit(self._send, config, photo, deepcopy(session.stats), attention.continuous)

    def _submit_audio(self, config, decision):
        self.audio_future = self.executor.submit(self.output, config, decision)

    def _send(self, config, photo, stats, duration):
        self.email.send(config, photo, stats, duration)
        if config.keep_photos:
            folder = DATA / "evidence"
            folder.mkdir(exist_ok=True)
            (folder / f"accountability-{time.time_ns()}.jpg").write_bytes(photo)

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.poll()
