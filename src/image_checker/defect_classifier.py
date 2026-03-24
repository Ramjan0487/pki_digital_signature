"""
UC-02 · Check 3 — Biometric defect classification
Detects: closed eyes, occluded ears, partial face occlusion
Uses MediaPipe Face Mesh (468 landmarks)
"""
import cv2
import numpy as np
import math

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False

# MediaPipe Face Mesh landmark indices
LEFT_EYE_TOP     = 159
LEFT_EYE_BOTTOM  = 145
LEFT_EYE_LEFT    = 33
LEFT_EYE_RIGHT   = 133
RIGHT_EYE_TOP    = 386
RIGHT_EYE_BOTTOM = 374
RIGHT_EYE_LEFT   = 362
RIGHT_EYE_RIGHT  = 263

LEFT_EAR_LANDMARK  = 234
RIGHT_EAR_LANDMARK = 454

EYE_OPEN_RATIO_THRESHOLD  = 0.22    # below = eye considered closed
EAR_EDGE_MARGIN           = 0.04    # ear must be at least 4% from image edge
FACE_COVERAGE_THRESHOLD   = 0.82    # < 82% landmark coverage = occlusion


def classify_defects(image_bytes: bytes) -> dict:
    """
    Run landmark-based defect checks: eyes, ears, face completeness.
    Returns dict with 'pass', 'defects' (list), and 'message'.
    """
    if not _MP_AVAILABLE:
        return {"pass": True, "defects": [], "message": "MediaPipe not available — check skipped."}

    arr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_bgr.shape[:2]

    mp_mesh = mp.solutions.face_mesh
    with mp_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.6,
    ) as mesh:
        results = mesh.process(img_rgb)

    if not results.multi_face_landmarks:
        return _fail(["NO_LANDMARKS"], "Could not extract facial landmarks. Please retake the photo.")

    lm = results.multi_face_landmarks[0].landmark
    defects = []
    messages = []

    # ── Eye openness check ────────────────────────────────────────────────────
    left_ear_val  = _eye_aspect_ratio(lm, LEFT_EYE_TOP, LEFT_EYE_BOTTOM, LEFT_EYE_LEFT, LEFT_EYE_RIGHT)
    right_ear_val = _eye_aspect_ratio(lm, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM, RIGHT_EYE_LEFT, RIGHT_EYE_RIGHT)

    if left_ear_val < EYE_OPEN_RATIO_THRESHOLD and right_ear_val < EYE_OPEN_RATIO_THRESHOLD:
        defects.append("EYES_CLOSED")
        messages.append("Both eyes appear to be closed. Please look directly at the camera with eyes fully open.")
    elif left_ear_val < EYE_OPEN_RATIO_THRESHOLD:
        defects.append("LEFT_EYE_CLOSED")
        messages.append("Your left eye appears closed or obscured. Please ensure both eyes are clearly visible.")
    elif right_ear_val < EYE_OPEN_RATIO_THRESHOLD:
        defects.append("RIGHT_EYE_CLOSED")
        messages.append("Your right eye appears closed or obscured. Please ensure both eyes are clearly visible.")

    # ── Ear visibility check ─────────────────────────────────────────────────
    left_ear_lm  = lm[LEFT_EAR_LANDMARK]
    right_ear_lm = lm[RIGHT_EAR_LANDMARK]

    if left_ear_lm.x < EAR_EDGE_MARGIN or left_ear_lm.x > (1 - EAR_EDGE_MARGIN):
        defects.append("LEFT_EAR_OCCLUDED")
        messages.append("The left ear is not visible. Please remove hair, hat, or accessories covering your ear.")
    if right_ear_lm.x < EAR_EDGE_MARGIN or right_ear_lm.x > (1 - EAR_EDGE_MARGIN):
        defects.append("RIGHT_EAR_OCCLUDED")
        messages.append("The right ear is not visible. Please remove hair, hat, or accessories covering your ear.")

    # ── Face coverage / occlusion check ──────────────────────────────────────
    visible = sum(
        1 for l in lm
        if 0.01 < l.x < 0.99 and 0.01 < l.y < 0.99 and l.visibility > 0.5
        if hasattr(l, "visibility")
    )
    total = len(lm)
    # Fallback if visibility attribute not present
    if visible == 0:
        visible = sum(1 for l in lm if 0.01 < l.x < 0.99 and 0.01 < l.y < 0.99)

    coverage = visible / total if total else 0
    if coverage < FACE_COVERAGE_THRESHOLD:
        defects.append("FACE_PARTIALLY_OCCLUDED")
        messages.append(
            "Part of your face appears to be covered or cut off. "
            "Please remove sunglasses, masks, or hats and ensure your full face is in frame."
        )

    if defects:
        return {
            "pass": False,
            "defects": defects,
            "message": " ".join(messages),
            "eye_ratio_left": round(left_ear_val, 3),
            "eye_ratio_right": round(right_ear_val, 3),
            "face_coverage": round(coverage, 3),
        }

    return {
        "pass": True,
        "defects": [],
        "message": "Biometric defect check passed.",
        "eye_ratio_left": round(left_ear_val, 3),
        "eye_ratio_right": round(right_ear_val, 3),
        "face_coverage": round(coverage, 3),
    }


def _eye_aspect_ratio(lm, top_i, bot_i, left_i, right_i) -> float:
    """Eye Aspect Ratio (EAR) — standard blink detection metric."""
    top   = lm[top_i]
    bot   = lm[bot_i]
    left  = lm[left_i]
    right = lm[right_i]
    vertical   = math.dist((top.x,   top.y),   (bot.x,   bot.y))
    horizontal = math.dist((left.x,  left.y),  (right.x, right.y))
    return vertical / (horizontal + 1e-6)


def _fail(defects: list, message: str) -> dict:
    return {"pass": False, "defects": defects, "message": message}
