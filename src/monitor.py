"""Camera and inference stay off Tk's main thread; only the newest frame is retained."""
import queue
import threading
import time
from src.attention_engine import Observation


class Monitor:
    def __init__(self, config):
        self.config = config
        self.results = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def publish(self, item):
        try:
            self.results.get_nowait()
        except queue.Empty:
            pass
        self.results.put_nowait(item)

    def _run(self):
        camera = None
        try:
            from src.camera import Camera
            from src.phone_detector import PhoneDetector
            from src.hand_detector import HandDetector, near_phone
            phones = PhoneDetector(self.config)
            hands = HandDetector(self.config)
            if self.stop_event.is_set():
                return
            camera = Camera(self.config.camera_index)
            while not self.stop_event.is_set():
                frame = camera.read()
                detected = phones.detect(frame)
                person, wrists = hands.detect(frame)
                active = [p for p in detected if near_phone(p, wrists, self.config.wrist_margin)]
                observation = Observation(bool(detected), bool(active), person,
                                          max((p.confidence for p in active or detected), default=0.8))
                self.publish((time.monotonic(), observation, frame, detected, wrists, None))
        except Exception as error:
            self.publish((time.monotonic(), Observation(reliable=False), None, [], [],
                          f"Monitoring unavailable ({type(error).__name__}). Check dependencies, model downloads and camera access."))
        finally:
            if camera:
                camera.close()

    def stop(self):
        self.stop_event.set()
