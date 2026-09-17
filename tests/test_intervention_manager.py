from unittest.mock import Mock, patch
from src.attention_engine import Attention, State
from src.config import Config
from src.database import Database
from src.intervention_manager import InterventionManager
from src.session_manager import SessionManager


def setup(config=None):
    config = config or Config()
    db = Database(":memory:")
    session = SessionManager(db, config)
    session.start("Work", 60, 0)
    output = Mock()
    email = Mock()
    email.configured.return_value = True
    manager = InterventionManager(db, config, output, email)
    return db, session, manager, output, email


def test_threshold_cooldown_escalation_and_outcome():
    db, session, manager, output, _ = setup()
    manager.tick(session, Attention(State.PHONE_USE, 1, 60), 60)
    assert session.stats.warnings == 0
    for now, expected in [(61, 1), (62, 1), (121, 2), (181, 3)]:
        manager.tick(session, Attention(State.PHONE_USE, 1, now), now)
        if manager.audio_future:
            manager.audio_future.result()
        assert session.stats.warnings == expected
    assert output.call_args.args[1].repetitions == 3
    manager.tick(session, Attention(State.FOCUSED, 1, 0), 185)
    assert db.rows("SELECT response_time FROM interventions ORDER BY id DESC")[0]["response_time"] == 4
    manager.close()


def test_no_email_or_photo_by_default():
    _, session, manager, _, email = setup()
    with patch("src.intervention_manager.capture") as capture:
        manager.tick(session, Attention(State.PHONE_USE, 1, 61), 61, frame=object())
        capture.assert_not_called()
        email.send.assert_not_called()
    manager.close()


def test_email_cooldown_persists_across_manager_restart():
    config = Config(parent_mode=True, parent_email="parent@example.com")
    db, session, manager, _, email = setup(config)
    with patch("src.intervention_manager.capture", return_value=b"jpeg") as capture:
        manager.tick(session, Attention(State.PHONE_USE, 1, 61), 61, frame=object())
        manager.future.result()
        manager.poll()
        assert email.send.call_count == 1
        manager.close()
        manager = InterventionManager(db, config, Mock(), email)
        manager.tick(session, Attention(State.PHONE_USE, 1, 122), 122, frame=object())
        assert capture.call_count == 1
        assert db.rows("SELECT status FROM email_events ORDER BY id DESC")[0]["status"] == "sent"
        manager.close()


def test_break_suppresses_warnings_and_demo_suppresses_photos():
    _, session, manager, _, email = setup(Config(parent_mode=True, parent_email="parent@example.com"))
    session.mode = "break"
    manager.tick(session, Attention(State.PHONE_USE, 1, 61), 61, object())
    assert session.stats.warnings == 0
    session.mode = "running"
    manager.tick(session, Attention(State.PHONE_USE, 1, 62), 62, object(), allow_email=False)
    email.send.assert_not_called()
    manager.close()


def test_failed_email_is_logged_and_cooldown_applies():
    db, session, manager, _, email = setup(Config(parent_mode=True, parent_email="parent@example.com"))
    email.send.side_effect = RuntimeError("Private server error")
    with patch("src.intervention_manager.capture", return_value=b"jpeg"):
        manager.tick(session, Attention(State.PHONE_USE, 1, 61), 61, object())
        try:
            manager.future.result()
        except RuntimeError:
            pass
        manager.close()
    assert db.rows("SELECT status FROM email_events ORDER BY id DESC")[0]["status"] == "failed"
    assert "Private" not in manager.notice


def test_expired_email_cooldown_allows_next_email():
    db, session, manager, _, email = setup(Config(parent_mode=True, parent_email="parent@example.com"))
    db.execute("INSERT INTO email_events(session_id,timestamp,status) VALUES(?,?,?)",
               (session.id, "2000-01-01T00:00:00+00:00", "sent"))
    with patch("src.intervention_manager.capture", return_value=b"jpeg"):
        manager.tick(session, Attention(State.PHONE_USE, 1, 61), 61, object())
        manager.future.result()
        manager.close()
    email.send.assert_called_once()


def test_photo_encoding_error_does_not_stop_monitoring():
    _, session, manager, _, email = setup(Config(parent_mode=True, parent_email="parent@example.com"))
    with patch("src.intervention_manager.capture", side_effect=RuntimeError("encoder error")):
        manager.tick(session, Attention(State.PHONE_USE, 1, 61), 61, object())
    assert session.stats.warnings == 1
    email.send.assert_not_called()
    manager.close()


def test_away_is_not_a_successful_response():
    db, session, manager, _, _ = setup()
    manager.tick(session, Attention(State.PHONE_USE, 1, 61), 61)
    manager.tick(session, Attention(State.AWAY, 1, 0), 65)
    manager.tick(session, Attention(State.FOCUSED, 1, 0), 70)
    assert db.rows("SELECT response_time FROM interventions")[0]["response_time"] is None
    manager.close()
