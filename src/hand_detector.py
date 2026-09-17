"""Lightweight wrist proxy from YOLO pose; full finger/head tracking is future work."""


class HandDetector:
    def __init__(self, config):
        from ultralytics import YOLO
        from src.config import DATA
        self.config = config
        self.model = YOLO(str(DATA / "yolo11n-pose.pt"))

    def detect(self, frame):
        result = self.model.predict(frame, conf=self.config.detection_confidence, verbose=False, save=False)[0]
        wrists = []
        if result.keypoints is not None:
            for points in result.keypoints.data.tolist():
                for index in (9, 10):
                    x, y, confidence = points[index]
                    if confidence >= self.config.wrist_confidence:
                        wrists.append((x, y))
        return len(result.boxes) > 0, wrists


def near_phone(phone, wrists, margin):
    x1, y1, x2, y2 = phone.box
    padding = max(x2-x1, y2-y1) * margin
    return any(x1-padding <= x <= x2+padding and y1-padding <= y <= y2+padding for x, y in wrists)
