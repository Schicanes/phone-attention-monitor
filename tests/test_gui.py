"""Real Tk startup smoke test, skipped only on hosts without a display."""
import tkinter as tk
import pytest
from src.config import Config
from ui.main_window import MainWindow


def test_demo_dashboard_session_controls(tmp_path, monkeypatch):
    import ui.main_window as window
    monkeypatch.setattr(window, "DATA", tmp_path)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No graphical display")
    app = MainWindow(root, Config(alarm=False, voice=False), demo=True)
    try:
        root.update()
        app.start()
        app.tick()
        assert app.session.mode == "running"
        assert app.monitor is None
        app.pause()
        assert app.session.mode == "paused"
        app.pause()
        app.take_break()
        assert app.session.mode == "break"
        app.take_break()
        assert app.session.mode == "running"
        app.stop()
        assert app.session.id is None
        assert app.db.rows("SELECT ended FROM sessions")[0]["ended"]
    finally:
        app.close()


def test_normal_window_starts_without_opening_camera(tmp_path, monkeypatch):
    import ui.main_window as window
    monkeypatch.setattr(window, "DATA", tmp_path)
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("No graphical display")
    app = MainWindow(root, Config(), demo=False)
    try:
        root.update()
        assert app.status.get() == "MONITORING OFF"
        assert app.monitor is None
        assert not app.config.parent_mode
    finally:
        app.close()
