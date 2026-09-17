"""One explicitly consented photo, encoded in memory; no temporary disk file."""
from datetime import datetime, timezone


def capture(frame, config):
    if not config.parent_mode:
        raise PermissionError("Photo consent is disabled")
    import cv2
    photo = frame.copy()
    cv2.putText(photo, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    ok, encoded = cv2.imencode(".jpg", photo)
    if not ok:
        raise RuntimeError("Unable to encode photo")
    return encoded.tobytes()
