"""
AI Face Detection Service
OpenCV: clarity (Laplacian blur, brightness, contrast, resolution)
MediaPipe Face Detection: presence, count, size
MediaPipe Face Mesh (468 landmarks): eye openness, ear visibility, face occlusion
"""
import time
import math
import cv2
import numpy as np

try:
    import mediapipe as mp
    _MEDIAPIPE = True
except ImportError:
    _MEDIAPIPE = False

# ── Landmark indices (MediaPipe Face Mesh) ────────────────────────────────────
L_EYE_TOP, L_EYE_BOT, L_EYE_L, L_EYE_R   = 159, 145, 33,  133
R_EYE_TOP, R_EYE_BOT, R_EYE_L, R_EYE_R   = 386, 374, 362, 263
L_EAR_LM, R_EAR_LM                         = 234, 454
NOSE_TIP                                    = 1


class FaceDetectionResult:
    """Structured result returned by detect()."""
    def __init__(self):
        self.passed         = False
        self.defect_code    = None
        self.defect_message = None
        self.blur_score     = 0.0
        self.brightness     = 0.0
        self.face_confidence= 0.0
        self.eye_ratio_left = 0.0
        self.eye_ratio_right= 0.0
        self.face_coverage  = 0.0
        self.duration_ms    = 0.0
        self.annotated_img  = None   # bytes: JPEG with drawn landmarks

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "annotated_img"}


class FaceDetector:
    """
    Run all detection checks in sequence.
    First failure stops the pipeline and returns the defect.
    """

    def __init__(self, config: dict):
        self.blur_threshold    = config.get("BLUR_THRESHOLD",    80.0)
        self.min_brightness    = config.get("MIN_BRIGHTNESS",    40.0)
        self.max_brightness    = config.get("MAX_BRIGHTNESS",   220.0)
        self.eye_open_ratio    = config.get("EYE_OPEN_RATIO",    0.22)
        self.ear_edge_margin   = config.get("EAR_EDGE_MARGIN",   0.04)
        self.face_min_coverage = config.get("FACE_MIN_COVERAGE", 0.82)
        self.face_confidence   = config.get("FACE_CONFIDENCE",   0.70)

    def detect(self, image_bytes: bytes) -> FaceDetectionResult:
        r = FaceDetectionResult()
        t0 = time.perf_counter()

        # ── Decode ────────────────────────────────────────────────────────────
        arr = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return self._fail(r, "INVALID_IMAGE",
                              "The uploaded file could not be decoded as an image.")

        h, w = img_bgr.shape[:2]
        if w < 300 or h < 300:
            return self._fail(r, "IMAGE_TOO_SMALL",
                              f"Photo must be at least 300×300 px. Got {w}×{h}.")

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # ── Check 1: Blur ─────────────────────────────────────────────────────
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        r.blur_score = round(blur, 2)
        if blur < self.blur_threshold:
            return self._fail(r, "IMAGE_TOO_BLURRY",
                              f"Photo is too blurry (score {blur:.1f}). "
                              "Retake with a steady hand in good lighting.")

        # ── Check 2: Brightness ───────────────────────────────────────────────
        brightness = float(gray.mean())
        r.brightness = round(brightness, 2)
        if brightness < self.min_brightness:
            return self._fail(r, "IMAGE_TOO_DARK",
                              f"Photo is too dark (brightness {brightness:.1f}). "
                              "Use a well-lit room facing a window or light source.")
        if brightness > self.max_brightness:
            return self._fail(r, "IMAGE_TOO_BRIGHT",
                              f"Photo is overexposed (brightness {brightness:.1f}). "
                              "Avoid direct flash and bright backgrounds.")

        # ── Check 3: Contrast ─────────────────────────────────────────────────
        contrast = float(gray.std())
        if contrast < 30.0:
            return self._fail(r, "LOW_CONTRAST",
                              "Photo has very low contrast. "
                              "Use a plain light-coloured background.")

        if not _MEDIAPIPE:
            r.passed = True
            r.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            return r

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # ── Check 4: Face presence ────────────────────────────────────────────
        mp_fd = mp.solutions.face_detection
        with mp_fd.FaceDetection(model_selection=1,
                                  min_detection_confidence=self.face_confidence) as fd:
            fd_results = fd.process(img_rgb)

        if not fd_results.detections:
            return self._fail(r, "NO_FACE_DETECTED",
                              "No face detected. Upload a clear, front-facing passport photo.")
        if len(fd_results.detections) > 1:
            return self._fail(r, "MULTIPLE_FACES",
                              f"{len(fd_results.detections)} faces found. "
                              "The photo must show one person only.")

        det = fd_results.detections[0]
        r.face_confidence = round(float(det.score[0]), 3)
        bb = det.location_data.relative_bounding_box
        if bb.width * bb.height < 0.05:
            return self._fail(r, "FACE_TOO_SMALL",
                              "Face is too small in the frame. "
                              "Position the camera so your face fills most of the photo.")

        # ── Check 5: Landmarks — eyes, ears, coverage ─────────────────────────
        mp_mesh = mp.solutions.face_mesh
        with mp_mesh.FaceMesh(static_image_mode=True, max_num_faces=1,
                               refine_landmarks=True,
                               min_detection_confidence=0.6) as mesh:
            mesh_results = mesh.process(img_rgb)

        if not mesh_results.multi_face_landmarks:
            return self._fail(r, "NO_LANDMARKS",
                              "Could not extract facial landmarks. Retake the photo.")

        lm = mesh_results.multi_face_landmarks[0].landmark

        # Eye aspect ratios
        lear = self._ear(lm, L_EYE_TOP, L_EYE_BOT, L_EYE_L, L_EYE_R)
        rear = self._ear(lm, R_EYE_TOP, R_EYE_BOT, R_EYE_L, R_EYE_R)
        r.eye_ratio_left  = round(lear, 3)
        r.eye_ratio_right = round(rear, 3)

        if lear < self.eye_open_ratio and rear < self.eye_open_ratio:
            return self._fail(r, "EYES_CLOSED",
                              "Both eyes appear closed. Look directly at the camera with eyes fully open.")
        if lear < self.eye_open_ratio:
            return self._fail(r, "LEFT_EYE_CLOSED",
                              "Left eye appears closed or obscured. Ensure both eyes are clearly visible.")
        if rear < self.eye_open_ratio:
            return self._fail(r, "RIGHT_EYE_CLOSED",
                              "Right eye appears closed or obscured. Ensure both eyes are clearly visible.")

        # Ear visibility
        lm_lear = lm[L_EAR_LM]
        lm_rear = lm[R_EAR_LM]
        if lm_lear.x < self.ear_edge_margin or lm_lear.x > (1 - self.ear_edge_margin):
            return self._fail(r, "LEFT_EAR_OCCLUDED",
                              "Left ear not visible. Remove hair, hat, or accessories covering your ear.")
        if lm_rear.x < self.ear_edge_margin or lm_rear.x > (1 - self.ear_edge_margin):
            return self._fail(r, "RIGHT_EAR_OCCLUDED",
                              "Right ear not visible. Remove hair, hat, or accessories covering your ear.")

        # Face coverage
        visible = sum(1 for l in lm if 0.01 < l.x < 0.99 and 0.01 < l.y < 0.99)
        coverage = visible / len(lm)
        r.face_coverage = round(coverage, 3)
        if coverage < self.face_min_coverage:
            return self._fail(r, "FACE_OCCLUDED",
                              "Part of your face is covered or out of frame. "
                              "Remove sunglasses/masks and ensure your full face is visible.")

        # ── All checks passed — annotate image ───────────────────────────────
        annotated = img_bgr.copy()
        self._draw_landmarks(annotated, lm, w, h)
        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
        r.annotated_img = buf.tobytes()

        r.passed      = True
        r.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return r

    # ── Private helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _ear(lm, ti, bi, li, ri) -> float:
        """Eye Aspect Ratio (standard blink detection metric)."""
        v = math.dist((lm[ti].x, lm[ti].y), (lm[bi].x, lm[bi].y))
        h = math.dist((lm[li].x, lm[li].y), (lm[ri].x, lm[ri].y))
        return v / (h + 1e-6)

    @staticmethod
    def _draw_landmarks(img, landmarks, w, h):
        """Draw key landmarks on the annotated preview image."""
        key_lm = [L_EYE_TOP, L_EYE_BOT, L_EYE_L, L_EYE_R,
                  R_EYE_TOP, R_EYE_BOT, R_EYE_L, R_EYE_R,
                  L_EAR_LM, R_EAR_LM, NOSE_TIP]
        for idx in key_lm:
            lm = landmarks[idx]
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(img, (cx, cy), 3, (0, 255, 0), -1)
        cv2.putText(img, "ACCEPTED", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 0), 2)

    @staticmethod
    def _fail(r: FaceDetectionResult, code: str, msg: str) -> FaceDetectionResult:
        r.passed         = False
        r.defect_code    = code
        r.defect_message = msg
        return r
