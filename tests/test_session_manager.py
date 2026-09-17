import pytest
from src.attention_engine import Attention, State
from src.config import Config
from src.database import Database
from src.session_manager import SessionManager


def test_session_accounting_pause_break_and_pickups():
    db = Database(":memory:")
    session = SessionManager(db, Config())
    session.start("Homework", 60, 0)
    session.update(Attention(State.FOCUSED, 1, 0), 0)
    for second in range(1, 11):
        session.update(Attention(State.FOCUSED, 1, 0), second)
    assert session.stats.focus == session.stats.longest_focus == 10
    session.update(Attention(State.PHONE_GLANCE, 1, 1), 10)
    session.update(Attention(State.PHONE_USE, 1, 3), 12)
    session.set_mode("paused", 13)
    assert session.stats.phone == 3
    session.set_mode("running", 100)
    assert session.stats.elapsed == 13
    session.set_mode("break", 100)
    session.advance(102)
    assert session.stats.elapsed == 15
    assert session.stats.pickups == 1
    session.stop(103)
    assert db.rows("SELECT ended FROM sessions")[0]["ended"] is not None
    db.close()


def test_camera_stall_not_counted_as_focus():
    db = Database(":memory:")
    session = SessionManager(db, Config())
    session.start("Work", 1, 0)
    session.update(Attention(State.FOCUSED, 1, 0), 0)
    session.advance(40)
    assert session.stats.elapsed == 40
    assert session.stats.focus == 0
    session.advance(100)
    assert session.stats.elapsed == 60


@pytest.mark.parametrize("task,minutes", [("", 1), ("Work", 0), ("Work", float("nan"))])
def test_invalid_session(task, minutes):
    session = SessionManager(Database(":memory:"), Config())
    with pytest.raises(ValueError):
        session.start(task, minutes, 0)
