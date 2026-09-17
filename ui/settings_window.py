from dataclasses import replace
import tkinter as tk
from tkinter import messagebox, ttk
from src.config import CONSENT


def build_settings(parent, app):
    ttk.Label(parent, text="Your preferences", style="Title.TLabel").pack(anchor="w", pady=12)
    ttk.Label(parent, text="Stop your session before saving changes. Credentials belong only in .env.").pack(anchor="w")
    fields = {}
    for label, name in [("Phone threshold (seconds)", "phone_threshold"), ("Warning cooldown (seconds)", "warning_cooldown"),
                        ("Email cooldown (seconds)", "email_cooldown"), ("Your name", "user_name"),
                        ("Parent email", "parent_email"), ("Camera index", "camera_index"), ("Email subject", "email_subject")]:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=30).pack(side="left")
        fields[name] = tk.StringVar(value=str(getattr(app.config, name)))
        ttk.Entry(row, textvariable=fields[name], width=55).pack(side="left", fill="x", expand=True)
    for label, name in [("Alarm", "alarm"), ("Offline voice", "voice"), ("Adaptive rule-based agent", "agent_enabled"),
                        ("Parent Accountability Mode — captures and emails photos", "parent_mode"),
                        ("Keep emailed photos locally", "keep_photos")]:
        fields[name] = tk.BooleanVar(value=getattr(app.config, name))
        ttk.Checkbutton(parent, text=label, variable=fields[name]).pack(anchor="w", pady=2)
    ttk.Label(parent, text="Email body (placeholders: USER_NAME, PHONE_DURATION, FOCUS_TIME, PHONE_PICKUPS, WARNING_COUNT)").pack(anchor="w", pady=5)
    body = tk.Text(parent, height=9, bg="#182335", fg="#e6edf7", insertbackground="white", wrap="word")
    body.insert("1.0", app.config.email_body)
    body.pack(fill="both", expand=True)

    def save():
        if app.session.id is not None:
            messagebox.showinfo("Session active", "Stop your session before saving settings.")
            return
        try:
            values = {name: variable.get() for name, variable in fields.items()}
            for name in ("phone_threshold", "warning_cooldown", "email_cooldown"):
                values[name] = float(values[name])
            values["camera_index"] = int(values["camera_index"])
            values["email_body"] = body.get("1.0", "end-1c")
            config = replace(app.config, **values)
            config.validate()
            if config.parent_mode and not app.config.parent_mode:
                if not messagebox.askyesno("Explicit photo and email consent", CONSENT):
                    fields["parent_mode"].set(False)
                    return
            config.save()
            app.config = config
            app.session.config = app.engine.config = app.interventions.config = config
            app.threshold.set(str(config.phone_threshold))
            messagebox.showinfo("Saved", "Settings saved locally.")
        except (ValueError, KeyError, IndexError) as error:
            messagebox.showerror("Invalid settings", str(error))
    ttk.Button(parent, text="Save settings", command=save).pack(anchor="e", pady=8)
