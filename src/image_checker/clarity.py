"""
UC-02 · Check 1 — Image clarity (blur, brightness, contrast)
"""
import cv2
import numpy as np

BLUR_THRESHOLD       = 80.0    # Laplacian variance — below = too blurry
MIN_BRIGHTNESS       = 40.0    # mean pixel value — below = too dark
MAX_BRIGHTNESS       = 220.0   # mean pixel value — above = overexposed
MIN_CONTRAST_STD     = 30.0    # pixel std dev — below = flat/washed out
MIN_WIDTH            = 300     # pixels
MIN_HEIGHT           = 300     # pixels


def check_clarity(image_bytes: bytes) -> dict:
    """
    Run blur + brightness + resolution checks on a raw image byte string.
    Returns a dict with 'pass' (bool), 'defect' (str or None), and 'message'.
    """
    arr = np.frombuffer(image_bytes, np.uint8)
    img_color = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img_color is None:
        return _fail("INVALID_IMAGE", "The uploaded file could not be read as an image.")

    h, w = img_color.shape[:2]
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        return _fail(
            "IMAGE_TOO_SMALL",
            f"Photo must be at least {MIN_WIDTH}×{MIN_HEIGHT} pixels. "
            f"Uploaded image is {w}×{h}.",
        )

    gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

    # Blur — Laplacian variance
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < BLUR_THRESHOLD:
        return _fail(
            "IMAGE_TOO_BLURRY",
            f"The photo is too blurry (sharpness score: {blur_score:.1f}). "
            "Please retake the photo with a steady hand in good light.",
            extra={"blur_score": round(blur_score, 2)},
        )

    # Brightness
    brightness = float(gray.mean())
    if brightness < MIN_BRIGHTNESS:
        return _fail(
            "IMAGE_TOO_DARK",
            f"The photo is too dark (brightness: {brightness:.1f}). "
            "Please retake in a well-lit environment.",
            extra={"brightness": round(brightness, 2)},
        )
    if brightness > MAX_BRIGHTNESS:
        return _fail(
            "IMAGE_TOO_BRIGHT",
            f"The photo is overexposed (brightness: {brightness:.1f}). "
            "Please avoid direct flash or bright backgrounds.",
            extra={"brightness": round(brightness, 2)},
        )

    # Contrast
    contrast = float(gray.std())
    if contrast < MIN_CONTRAST_STD:
        return _fail(
            "LOW_CONTRAST",
            "The photo has very low contrast — it may be washed out or foggy. "
            "Please use a plain, light-coloured background.",
            extra={"contrast": round(contrast, 2)},
        )

    return {
        "pass": True,
        "defect": None,
        "message": "Image clarity check passed.",
        "blur_score": round(blur_score, 2),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
    }


def _fail(defect: str, message: str, extra: dict = None) -> dict:
    result = {"pass": False, "defect": defect, "message": message}
    if extra:
        result.update(extra)
    return result
