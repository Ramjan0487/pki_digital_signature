"""
Tests for UC-02 — Image quality and defect detection
"""
import pytest
import numpy as np
import cv2
from src.image_checker.clarity import check_clarity


def make_image_bytes(h=400, w=400, blur=0, brightness=128) -> bytes:
    """Generate a synthetic test image."""
    img = np.ones((h, w, 3), dtype=np.uint8) * brightness
    # Draw a simple face-like shape so detectors have something
    cv2.circle(img, (w//2, h//2), min(h,w)//3, (200, 180, 160), -1)
    cv2.circle(img, (w//2 - 50, h//2 - 30), 15, (80, 60, 40), -1)  # left eye
    cv2.circle(img, (w//2 + 50, h//2 - 30), 15, (80, 60, 40), -1)  # right eye
    if blur > 0:
        img = cv2.GaussianBlur(img, (blur*2+1, blur*2+1), blur)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class TestClarity:
    def test_sharp_image_passes(self):
        img = make_image_bytes(blur=0, brightness=128)
        result = check_clarity(img)
        assert result["pass"] is True

    def test_very_blurry_image_fails(self):
        img = make_image_bytes(blur=25, brightness=128)
        result = check_clarity(img)
        assert result["pass"] is False
        assert result["defect"] == "IMAGE_TOO_BLURRY"

    def test_dark_image_fails(self):
        img = make_image_bytes(blur=0, brightness=10)
        result = check_clarity(img)
        assert result["pass"] is False
        assert result["defect"] == "IMAGE_TOO_DARK"

    def test_bright_image_fails(self):
        img = make_image_bytes(blur=0, brightness=250)
        result = check_clarity(img)
        assert result["pass"] is False
        assert result["defect"] == "IMAGE_TOO_BRIGHT"

    def test_small_image_fails(self):
        img = make_image_bytes(h=100, w=100, blur=0, brightness=128)
        result = check_clarity(img)
        assert result["pass"] is False
        assert result["defect"] == "IMAGE_TOO_SMALL"

    def test_invalid_bytes_fails(self):
        result = check_clarity(b"not an image")
        assert result["pass"] is False
        assert result["defect"] == "INVALID_IMAGE"
