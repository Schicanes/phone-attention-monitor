import logging
import queue
import time
import tkinter as tk
from tkinter import messagebox, ttk
from src.analytics import personalization, summary
from src.attention_engine import Attention, AttentionEngine, Observation, State
from src.config import DATA
from src.database import Database
from src.intervention_manager import InterventionManager
from src.monitor import Monitor
from src.session_manager import SessionManager
from ui.dashboard import build_dashboard
from ui.settings_window import build_settings


def clock(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"


class MainWindow:
    def __init__(self, root, config, demo=False):
        self.root, self.config, self.demo = root, config, demo
        DATA.mkdir(exist_ok=True)
        self.db = Database(DATA / ("demo.db" if demo else "attention.db"))
        self.session = SessionManager(self.db, config)
        self.engine = AttentionEngine(config)
        self.interventions = InterventionManager(self.db, config)
        self.monitor = None
        self.retiring = []
        self.attention = Attention(State.UNCERTAIN, 0, 0)
        self.last_frame_at = 0
        root.title("Phone Attention Monitor" + (" · DEMO" if demo else ""))
        root.geometry("1020x820")
        root.minsize(900, 760)
        root.configure(bg="#101827")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background="#101827", foreground="#e6edf7", fieldbackground="#223047", font=("Segoe UI", 11))
        style.configure("TButton", padding=9, background="#284b63")
        style.map("TButton", background=[("active", "#356c83")])
        style.configure("TNotebook.Tab", padding=(20, 12))
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"))
        style.configure("Metrics.TLabel", font=("Consolas", 19))
        self.status = tk.StringVar(value="MONITORING OFF")
        ttk.Label(root, text="PHONE / ATTENTION", style="Title.TLabel").pack(anchor="w", padx=24, pady=(18, 4))
        ttk.Label(root, textvariable=self.status, foreground="#60d8bf").pack(anchor="w", padx=24, pady=(0, 14))
        self.task, self.minutes, self.threshold = tk.StringVar(value="Deep work"), tk.StringVar(value="60"), tk.StringVar(value=str(config.phone_threshold))
        self.metrics = tk.StringVar(value="Ready when you are.")
        self.notice = tk.StringVar(value="Demo mode never opens the camera or sends email." if demo else "")
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        pages = {}
        for title in ("Dashboard", "Live Monitor", "Analytics", "Settings"):
            pages[title] = ttk.Frame(notebook, padding=18)
            notebook.add(pages[title], text=title)
        build_dashboard(pages["Dashboard"], self)
        build_settings(pages["Settings"], self)
        self.preview = ttk.Label(pages["Live Monitor"], text="Camera preview appears during a focus session.")
        self.preview.pack(expand=True)
        self.classification = tk.StringVar(value="UNCERTAIN")
        ttk.Label(pages["Live Monitor"], textvariable=self.classification).pack(pady=10)
        self.demo_state = tk.StringVar(value="Focused")
        if demo:
            ttk.Label(pages["Live Monitor"], text="Simulate a signal:").pack()
            ttk.Combobox(pages["Live Monitor"], textvariable=self.demo_state, state="readonly",
                         values=["Focused", "Phone use", "Desk phone", "Away", "Uncertain"]).pack()
        self.analytics_text = tk.StringVar()
        ttk.Button(pages["Analytics"], text="Refresh daily / weekly statistics", command=self.refresh_analytics).pack(anchor="w")
        ttk.Label(pages["Analytics"], textvariable=self.analytics_text, justify="left").pack(anchor="w", pady=16)
        ttk.Label(pages["Analytics"], text="Latest session timeline · green focus / amber phone / gray other").pack(anchor="w")
        self.timeline = tk.Canvas(pages["Analytics"], height=65, bg="#182335", highlightthickness=0)
        self.timeline.pack(fill="x", pady=12)
        self.refresh_analytics()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(150, self.tick)

    def start(self):
        if self.session.id is not None:
            return
        self.retiring = [m for m in self.retiring if m.thread.is_alive()]
        if self.retiring:
            self.notice.set("Camera worker is stopping. Please wait a moment before restarting.")
            return
        try:
            threshold = float(self.threshold.get())
            if not 0 < threshold <= 86400:
                raise ValueError("Phone threshold must be between 0 and 86400 seconds")
            self.session.start(self.task.get(), float(self.minutes.get()), time.monotonic())
            self.config.phone_threshold = threshold
            self.engine.reset()
            self.interventions.reset_session()
            self.last_frame_at = time.monotonic()
            if not self.demo:
                self.monitor = Monitor(self.config)
                self.monitor.start()
            self.status.set("DEMO · NO CAMERA" if self.demo else "STARTING CAMERA · loading models")
        except ValueError as error:
            messagebox.showerror("Session settings", str(error))

    def pause(self):
        if self.session.id is not None:
            self.session.set_mode("running" if self.session.mode == "paused" else "paused", time.monotonic())
            self.engine.reset()
            self.interventions.pending.clear()

    def take_break(self):
        if self.session.id is not None:
            self.session.set_mode("running" if self.session.mode == "break" else "break", time.monotonic())
            self.engine.reset()
            self.interventions.pending.clear()

    def stop(self):
        if self.monitor:
            self.monitor.stop()
            self.retiring.append(self.monitor)
            self.monitor = None
        self.session.stop(time.monotonic())
        self.engine.reset()
        self.interventions.pending.clear()
        self.status.set("STOPPING CAMERA" if any(m.thread.is_alive() for m in self.retiring) else "MONITORING OFF")
        self.preview.configure(image="", text="Monitoring stopped. Camera worker is releasing the device.")
        self.preview.image = None
        self.refresh_analytics()

    def tick(self):
        self.retiring = [m for m in self.retiring if m.thread.is_alive()]
        if self.session.id is None and not self.retiring:
            self.status.set("MONITORING OFF")
        self.interventions.poll()
        if self.interventions.notice:
            self.notice.set(self.interventions.notice)
        now = time.monotonic()
        if self.session.id is not None:
            item = None
            if self.demo:
                selected = self.demo_state.get()
                item = (now, Observation(selected in ("Phone use", "Desk phone"), selected == "Phone use",
                                         selected != "Away", 0.9, selected != "Uncertain"), None, [], [], None)
            elif self.monitor:
                try:
                    item = self.monitor.results.get_nowait()
                except queue.Empty:
                    pass
            if item:
                timestamp, observation, frame, phones, wrists, error = item
                self.last_frame_at = timestamp
                if error:
                    self.notice.set(error)
                    self.session.previous = State.UNCERTAIN
                    self.stop()
                else:
                    self.status.set("DEMO · NO CAMERA" if self.demo else "CAMERA MONITORING ACTIVE · local processing")
                    self.attention = self.engine.update(observation, now, self.session.mode != "running")
                    self.session.update(self.attention, now)
                    self.interventions.tick(self.session, self.attention, now, frame, allow_email=not self.demo)
                    if frame is not None:
                        self.show_frame(frame, phones, wrists)
            elif now - self.last_frame_at > self.config.max_frame_gap:
                self.attention = self.engine.update(Observation(reliable=False), now)
                self.session.previous = State.UNCERTAIN
                self.session.update(self.attention, now)
                self.interventions.pending.clear()
                self.status.set("CAMERA SIGNAL UNAVAILABLE · timers uncertain")
            self.render_metrics()
            if self.session.id is not None and self.session.stats.elapsed >= self.session.planned:
                self.notice.set("Focus session complete. Well done making time for your task.")
                self.stop()
        self.root.after(150, self.tick)

    def render_metrics(self):
        s = self.session.stats
        self.metrics.set(f"{self.session.task}\n\n{clock(s.elapsed)} / {clock(self.session.planned)}     {self.session.mode.upper()}\n\n"
                         f"{self.attention.state}\n\nFocus streak  {clock(s.focus_streak)}\nPhone time    {clock(s.phone)}\n"
                         f"Phone now     {clock(self.attention.continuous)}\nPickups       {s.pickups}     Warnings  {s.warnings}")
        self.classification.set(f"{self.attention.state} · confidence {self.attention.confidence:.0%} · continuous {clock(self.attention.continuous)}")

    def show_frame(self, frame, phones, wrists):
        import cv2
        from PIL import Image, ImageTk
        image = frame.copy()
        for phone in phones:
            x1, y1, x2, y2 = map(int, phone.box)
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 210, 255), 2)
            cv2.putText(image, f"Phone {phone.confidence:.0%}", (x1, max(y1-8, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 210, 255), 1)
        for x, y in wrists:
            cv2.circle(image, (int(x), int(y)), 6, (170, 240, 50), -1)
        image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        image.thumbnail((820, 500))
        self.preview.image = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.preview.image, text="")

    def refresh_analytics(self):
        lines = []
        for title, days in [("TODAY", 1), ("LAST 7 DAYS", 7)]:
            s = summary(self.db, days)
            lines.append(f"{title}\nFocus {clock(s['focus'])}   Phone {clock(s['phone'])}   Pickups {s['pickups']}   Warnings {s['warnings']}\n"
                         f"Distractions/hour {s['per_hour']:.1f}   Longest focus {clock(s['longest'])}   Average phone {clock(s['average_phone'])}\n")
        history = personalization(self.db)
        lines.append(f"Most distracted hour: {history['most_distracted_hour'] or '—'}\nResponse time by intervention: {history['response_seconds']}")
        self.analytics_text.set("\n".join(lines))
        rows = self.db.rows("SELECT state,duration FROM attention_events WHERE session_id=(SELECT MAX(id) FROM sessions) ORDER BY id")
        total = sum(row["duration"] for row in rows) or 1
        self.timeline.delete("all")
        x = 0
        width = max(self.timeline.winfo_width(), 800)
        for row in rows:
            end = x + width * row["duration"] / total
            color = "#60d8bf" if row["state"] == "FOCUSED" else "#f5c76c" if row["state"] in ("PHONE_USE", "PHONE_GLANCE") else "#536079"
            self.timeline.create_rectangle(x, 10, end, 55, fill=color, outline="")
            x = end

    def close(self):
        self.stop()
        self.interventions.close()
        self.db.close()
        logging.info("Application closed")
        self.root.destroy()
