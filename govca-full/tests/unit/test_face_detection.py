"""
tests/unit/test_face_detection.py
Unit tests for AI face detection pipeline — no real images required.
"""
import pytest
import numpy as np
import cv2
from app.services.face_detection import FaceDetector, FaceDetectionResult

DEFAULT_CFG = {
    "BLUR_THRESHOLD":    80.0,
    "MIN_BRIGHTNESS":    40.0,
    "MAX_BRIGHTNESS":    220.0,
    "EYE_OPEN_RATIO":    0.22,
    "EAR_EDGE_MARGIN":   0.04,
    "FACE_MIN_COVERAGE": 0.82,
    "FACE_CONFIDENCE":   0.70,
}


def _make_img(h=400, w=400, brightness=128, blur=0, noise=False) -> bytes:
    """Synthesise a test image as JPEG bytes."""
    img = np.ones((h, w, 3), dtype=np.uint8) * brightness
    # Simple face-like oval
    cv2.ellipse(img, (w//2, h//2), (w//4, h//3), 0, 0, 360, (200, 175, 150), -1)
    cv2.circle(img, (w//2 - 60, h//2 - 40), 20, (60, 40, 20), -1)   # left eye
    cv2.circle(img, (w//2 + 60, h//2 - 40), 20, (60, 40, 20), -1)   # right eye
    cv2.ellipse(img, (w//2, h//2 + 60), (40, 20), 0, 0, 180, (120, 60, 60), -1)  # mouth
    if noise:
        noise_arr = np.random.randint(0, 50, img.shape, dtype=np.uint8)
        img = cv2.add(img, noise_arr)
    if blur > 0:
        img = cv2.GaussianBlur(img, (blur * 2 + 1, blur * 2 + 1), blur)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class TestClarity:
    def setup_method(self):
        self.det = FaceDetector(DEFAULT_CFG)

    def test_sharp_normal_image_passes_clarity(self):
        r = self.det.detect(_make_img(brightness=128, blur=0))
        # MediaPipe may or may not find face in synthetic; clarity at least passes
        assert r.defect_code not in ("IMAGE_TOO_BLURRY", "IMAGE_TOO_DARK",
                                     "IMAGE_TOO_BRIGHT", "IMAGE_TOO_SMALL",
                                     "INVALID_IMAGE", "LOW_CONTRAST")

    def test_blurry_image_rejected(self):
        r = self.det.detect(_make_img(brightness=128, blur=30))
        assert r.passed is False
        assert r.defect_code == "IMAGE_TOO_BLURRY"

    def test_dark_image_rejected(self):
        r = self.det.detect(_make_img(brightness=5))
        assert r.passed is False
        assert r.defect_code == "IMAGE_TOO_DARK"

    def test_bright_image_rejected(self):
        r = self.det.detect(_make_img(brightness=252))
        assert r.passed is False
        assert r.defect_code == "IMAGE_TOO_BRIGHT"

    def test_too_small_image_rejected(self):
        r = self.det.detect(_make_img(h=100, w=100))
        assert r.passed is False
        assert r.defect_code == "IMAGE_TOO_SMALL"

    def test_invalid_bytes_rejected(self):
        r = self.det.detect(b"not an image at all")
        assert r.passed is False
        assert r.defect_code == "INVALID_IMAGE"

    def test_result_to_dict_excludes_annotated_img(self):
        r = FaceDetectionResult()
        r.annotated_img = b"\xff\xd8"
        d = r.to_dict()
        assert "annotated_img" not in d

    def test_blur_score_recorded(self):
        r = self.det.detect(_make_img(brightness=128, blur=0))
        assert r.blur_score > 0

    def test_brightness_recorded(self):
        r = self.det.detect(_make_img(brightness=128))
        assert 100 < r.brightness < 160


class TestFaceDetector:
    def setup_method(self):
        self.det = FaceDetector(DEFAULT_CFG)

    def test_duration_ms_always_set(self):
        r = self.det.detect(_make_img())
        assert r.duration_ms >= 0

    def test_custom_blur_threshold(self):
        cfg = {**DEFAULT_CFG, "BLUR_THRESHOLD": 10000.0}  # impossibly high
        det = FaceDetector(cfg)
        r   = det.detect(_make_img(brightness=128, blur=0))
        assert r.passed is False
        assert r.defect_code == "IMAGE_TOO_BLURRY"
