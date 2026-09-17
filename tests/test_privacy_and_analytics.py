import pytest
from src.analytics import personalization, summary
from src.config import Config
from src.database import Database
from src.email_service import EmailService
from src.screenshot_service import capture
from src.hand_detector import near_phone
from src.phone_detector import Phone


def test_consent_enforced_at_services():
    with pytest.raises(PermissionError):
        capture(object(), Config())
    with pytest.raises(PermissionError):
        EmailService().send(Config(), b"jpeg", None, 60)


def test_empty_analytics():
    db = Database(":memory:")
    assert summary(db)["phone"] == 0
    assert summary(db)["per_hour"] == 0
    assert personalization(db)["response_seconds"] == {}


def test_wrist_proximity():
    phone = Phone((100, 100, 150, 200), .9)
    assert near_phone(phone, [(120, 180)], .7)
    assert not near_phone(phone, [(400, 400)], .7)


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_config_rejects_invalid_thresholds(value):
    with pytest.raises(ValueError):
        Config(phone_threshold=value).validate()
