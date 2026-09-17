from dataclasses import dataclass


@dataclass
class Phone:
    box: tuple
    confidence: float


class PhoneDetector:
    def __init__(self, config):
        from ultralytics import YOLO
        from src.config import DATA
        self.config = config
        self.model = YOLO(str(DATA / "yolo11n.pt"))

    def detect(self, frame):
        result = self.model.predict(frame, classes=[67], conf=self.config.detection_confidence,
                                    verbose=False, save=False)[0]
        return [Phone(tuple(box.xyxy[0].tolist()), float(box.conf[0])) for box in result.boxes]
