import pytest
from src.attention_engine import AttentionEngine, Observation, State
from src.config import Config


def test_visible_desk_phone_is_not_usage():
    engine = AttentionEngine(Config())
    for second in range(100):
        result = engine.update(Observation(phone=True), second)
        assert result.state == State.UNCERTAIN
        assert result.continuous == 0


def test_smoothing_glance_and_sustained_use():
    engine = AttentionEngine(Config())
    assert engine.update(Observation(True, True), 0).state == State.UNCERTAIN
    assert engine.update(Observation(True, True), 1).state == State.PHONE_GLANCE
    assert engine.update(Observation(True, True), 3).state == State.PHONE_USE


def test_short_dropout_preserves_timer_but_long_dropout_resets():
    engine = AttentionEngine(Config())
    for second in range(65):
        result = engine.update(Observation(True, True), second)
    assert result.continuous == 64
    assert engine.update(Observation(), 65).continuous == 65
    assert engine.update(Observation(True, True), 66).continuous == 66
    engine.update(Observation(), 67)
    engine.update(Observation(), 68)
    assert engine.update(Observation(), 69).state == State.FOCUSED


@pytest.mark.parametrize("observation,on_break,state", [
    (Observation(), True, State.BREAK),
    (Observation(reliable=False), False, State.UNCERTAIN),
])
def test_break_and_invalid_signal_reset(observation, on_break, state):
    engine = AttentionEngine(Config())
    engine.update(Observation(True, True), 0)
    assert engine.update(observation, 1, on_break).state == state
    assert engine.update(Observation(True, True), 2).continuous == 0


def test_stale_frames_and_reverse_time():
    engine = AttentionEngine(Config())
    engine.update(Observation(True, True), 0)
    assert engine.update(Observation(True, True), 100).continuous == 0
    with pytest.raises(ValueError):
        engine.update(Observation(), 99)
