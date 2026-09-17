import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
from src.camera import Camera
from src.config import Config
from src.email_service import EmailService
from src.phone_detector import PhoneDetector
from src.session_manager import Stats


def test_camera_failure_releases_device():
    device = Mock()
    device.isOpened.return_value = False
    with patch.dict(sys.modules, {"cv2": SimpleNamespace(VideoCapture=Mock(return_value=device))}):
        with pytest.raises(RuntimeError, match="Cannot open"):
            Camera()
    device.release.assert_called_once()


def test_camera_disconnect():
    device = Mock()
    device.isOpened.return_value = True
    device.read.return_value = (False, None)
    cv = SimpleNamespace(VideoCapture=Mock(return_value=device), CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4)
    with patch.dict(sys.modules, {"cv2": cv}):
        camera = Camera()
        with pytest.raises(RuntimeError, match="disconnected"):
            camera.read()
        camera.close()
    device.release.assert_called_once()


def test_phone_adapter_does_not_save_frames():
    coordinates = Mock()
    coordinates.tolist.return_value = [10, 20, 30, 40]
    model = Mock()
    model.predict.return_value = [SimpleNamespace(boxes=[SimpleNamespace(xyxy=[coordinates], conf=[0.85])])]
    with patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=Mock(return_value=model))}):
        detector = PhoneDetector(Config())
        phone = detector.detect(object())[0]
    assert phone.box == (10, 20, 30, 40)
    assert phone.confidence == .85
    assert model.predict.call_args.kwargs["save"] is False
    assert model.predict.call_args.kwargs["classes"] == [67]


def test_email_attachment_and_tls(monkeypatch):
    for key, value in {"SMTP_HOST": "smtp.example.com", "SENDER_EMAIL": "sender@example.com",
                       "EMAIL_APP_PASSWORD": "test-only", "SMTP_PORT": "465"}.items():
        monkeypatch.setenv(key, value)
    with patch("src.email_service.smtplib.SMTP_SSL") as smtp:
        EmailService().send(Config(parent_mode=True, parent_email="parent@example.com"), b"jpeg", Stats(), 61)
    kwargs = smtp.call_args.kwargs
    assert kwargs["context"].check_hostname
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert message["To"] == "parent@example.com"
    assert len(list(message.iter_attachments())) == 1
