import logging


class Camera:
    def __init__(self, index=0):
        import cv2
        self.capture = cv2.VideoCapture(index)
        if not self.capture.isOpened():
            self.close()
            raise RuntimeError("Cannot open webcam. Check permissions and close other camera apps.")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        logging.info("Camera initialized")

    def read(self):
        ok, frame = self.capture.read()
        if not ok:
            raise RuntimeError("Camera disconnected. Stop and restart monitoring to reconnect.")
        return frame

    def close(self):
        self.capture.release()
