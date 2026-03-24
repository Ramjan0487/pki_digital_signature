"""
UC-02 · Check 2 — Face presence detection using MediaPipe
"""
import cv2
import numpy as np

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False

MIN_FACE_CONFIDENCE  = 0.70
EXPECTED_FACE_COUNT  = 1


def detect_face(image_bytes: bytes) -> dict:
    """
    Detect whether the image contains exactly one clear, forward-facing human face.
    Returns dict with 'pass', 'defect', 'message', and optional 'confidence'.
    """
    if not _MP_AVAILABLE:
        return _fail("MEDIAPIPE_NOT_INSTALLED",
                     "Face detection library is not installed on this server.")

    arr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    mp_face = mp.solutions.face_detection
    with mp_face.FaceDetection(
        model_selection=1,                    # 1 = full-range model (up to 5m)
        min_detection_confidence=MIN_FACE_CONFIDENCE,
    ) as detector:
        results = detector.process(img_rgb)

    if not results.detections:
        return _fail(
            "NO_FACE_DETECTED",
            "No face was detected in the uploaded photo. "
            "Please upload a clear, front-facing passport-style photo.",
        )

    if len(results.detections) > EXPECTED_FACE_COUNT:
        return _fail(
            "MULTIPLE_FACES_DETECTED",
            f"{len(results.detections)} faces detected. "
            "The photo must show only one person.",
        )

    detection = results.detections[0]
    confidence = float(detection.score[0])

    # Check face is reasonably large in the frame (not tiny/distant)
    bbox = detection.location_data.relative_bounding_box
    face_area_ratio = bbox.width * bbox.height
    if face_area_ratio < 0.05:
        return _fail(
            "FACE_TOO_SMALL",
            "The face is too small in the frame. "
            "Please position the camera closer so your face fills most of the photo.",
            extra={"face_area_ratio": round(face_area_ratio, 4)},
        )

    return {
        "pass": True,
        "defect": None,
        "message": "Face detection passed.",
        "confidence": round(confidence, 3),
        "face_area_ratio": round(face_area_ratio, 4),
    }


def _fail(defect: str, message: str, extra: dict = None) -> dict:
    result = {"pass": False, "defect": defect, "message": message}
    if extra:
        result.update(extra)
    return result
