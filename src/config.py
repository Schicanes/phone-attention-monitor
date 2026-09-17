"""Central thresholds and local, credential-free preferences."""
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONSENT = ("Parent Accountability Mode will capture and email webcam photographs when sustained "
           "phone usage is detected. Only enable this if you understand and consent to this behavior.")
DEFAULT_BODY = """Hello,

This is an automated accountability update from Phone Attention Monitor.
{USER_NAME} has been detected using their phone for approximately {PHONE_DURATION} seconds during a focus session.

Current session:
Focus time: {FOCUS_TIME} seconds
Phone pickups: {PHONE_PICKUPS}
Warnings issued: {WARNING_COUNT}

Photographic evidence from the moment of distraction is attached.
This automated system would like to provide an update regarding where the college investment is currently being spent.

Regards,
Phone Attention Monitor"""


@dataclass
class Config:
    phone_threshold: float = 60
    warning_cooldown: float = 60
    email_cooldown: float = 1800
    smoothing_seconds: float = 1.0
    dropout_seconds: float = 2.0
    glance_seconds: float = 3.0
    max_frame_gap: float = 3.0
    detection_confidence: float = 0.35
    wrist_confidence: float = 0.4
    wrist_margin: float = 0.7
    alarm: bool = True
    voice: bool = True
    parent_mode: bool = False
    keep_photos: bool = False
    agent_enabled: bool = True
    parent_email: str = ""
    user_name: str = "Student"
    email_subject: str = "College Investment Status Update"
    email_body: str = DEFAULT_BODY
    camera_index: int = 0

    def validate(self):
        for key in ("phone_threshold", "warning_cooldown", "email_cooldown", "max_frame_gap"):
            value = getattr(self, key)
            if not 0 < value < 86401:
                raise ValueError(f"{key} must be between 0 and 86400 seconds")
        self.email_body.format(USER_NAME="Student", PHONE_DURATION=60, FOCUS_TIME=100,
                               PHONE_PICKUPS=1, WARNING_COUNT=1)
        if self.parent_mode and ("@" not in self.parent_email or "\n" in self.parent_email):
            raise ValueError("Enter a valid parent email address")
        if "\n" in self.email_subject or "\r" in self.email_subject:
            raise ValueError("Email subject must be one line")

    def save(self):
        self.validate()
        DATA.mkdir(exist_ok=True)
        temp = DATA / "settings.tmp"
        temp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        temp.replace(DATA / "settings.json")

    @classmethod
    def load(cls):
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except ImportError:
            pass
        path = DATA / "settings.json"
        if path.exists():
            config = cls(**json.loads(path.read_text(encoding="utf-8")))
        else:
            config = cls(phone_threshold=float(os.getenv("PHONE_THRESHOLD_SECONDS", "60")),
                         email_cooldown=float(os.getenv("EMAIL_COOLDOWN_MINUTES", "30")) * 60,
                         parent_email=os.getenv("PARENT_EMAIL", ""),
                         user_name=os.getenv("USER_NAME", "Student"))
        config.validate()
        return config
