from tkinter import ttk


def build_dashboard(parent, app):
    ttk.Label(parent, text="Make room for deep work", style="Title.TLabel").pack(anchor="w", pady=(16, 8))
    ttk.Label(parent, text="Local camera processing · No recordings · You control accountability").pack(anchor="w")
    form = ttk.Frame(parent)
    form.pack(fill="x", pady=24)
    for label, variable in [("Task", app.task), ("Minutes", app.minutes), ("Phone threshold · seconds", app.threshold)]:
        column = ttk.Frame(form)
        column.pack(side="left", fill="x", expand=True, padx=(0, 16))
        ttk.Label(column, text=label).pack(anchor="w")
        ttk.Entry(column, textvariable=variable).pack(fill="x", pady=6)
    controls = ttk.Frame(parent)
    controls.pack(fill="x")
    for label, callback in [("Start focus", app.start), ("Pause / Resume", app.pause),
                            ("Break / Return", app.take_break), ("Stop", app.stop)]:
        ttk.Button(controls, text=label, command=callback).pack(side="left", padx=(0, 12))
    ttk.Label(parent, textvariable=app.metrics, style="Metrics.TLabel", justify="left").pack(anchor="w", pady=30)
    ttk.Label(parent, textvariable=app.notice, wraplength=800, foreground="#f5c76c").pack(anchor="w", pady=10)
