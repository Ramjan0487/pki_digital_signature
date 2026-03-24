# UC-02 · Image Quality & Defect Detection

## Problem

When an applicant uploads their passport photo at `/document/stepIndvdlDocument.sg`, the GovCA portal performs no automated quality or biometric validation. Problems that cause application rejection later include:

- **Blurry images** — motion blur, out-of-focus shots, low DPI scans.
- **Poor lighting** — overexposed (washed out) or underexposed (too dark) photos.
- **No face detected** — photo of a document, object, or wrong person submitted by mistake.
- **Eye defects** — both eyes closed, one eye obscured by hair or glasses.
- **Ear defects** — ears completely hidden by hair or a hat (required visible for biometric compliance).
- **Partial face** — face cut off at edges, or mask/sunglasses covering the lower or upper face.

These issues are currently discovered only during manual officer review, 1–5 business days after submission, causing delays and applicant frustration.

## Solution

An automated image validation pipeline triggered immediately on upload. It runs three sequential checks:

1. **Clarity check** — Laplacian variance for blur; histogram analysis for brightness/contrast.
2. **Face detection** — MediaPipe Face Detection to confirm a single, forward-facing face is present.
3. **Landmark & defect check** — MediaPipe Face Mesh (468 landmarks) to verify:
   - Both eyes are open (ear distance ratio above threshold).
   - Ears are partially visible (landmark presence left/right).
   - No significant occlusion across the nose, mouth, or forehead.

Each check has a pass/fail verdict. The first failure stops the pipeline and returns a structured error with the defect type, a human-readable message, and a confidence score.

## How To

### Step 1 — Receive upload
```
POST /api/validate-image
Content-Type: multipart/form-data
file: <photo.jpg>
application_id: "APP-20240312-001"
user_email: "applicant@example.com"
```

### Step 2 — Clarity check
```python
# src/image_checker/clarity.py
import cv2, numpy as np

def check_clarity(image_bytes: bytes) -> dict:
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    score = cv2.Laplacian(img, cv2.CV_64F).var()
    brightness = img.mean()
    return {
        "pass": score > 80 and 40 < brightness < 220,
        "blur_score": round(score, 2),
        "brightness": round(brightness, 2),
        "defect": None if score > 80 else "IMAGE_TOO_BLURRY"
    }
```

### Step 3 — Face detection
```python
# src/image_checker/face_detector.py
import mediapipe as mp

def detect_face(image_bytes: bytes) -> dict:
    mp_face = mp.solutions.face_detection
    with mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.7) as fd:
        img = decode_image(image_bytes)
        results = fd.process(img)
        if not results.detections or len(results.detections) != 1:
            return {"pass": False, "defect": "NO_FACE_DETECTED"}
        return {"pass": True, "confidence": results.detections[0].score[0]}
```

### Step 4 — Landmark defect check
```python
# src/image_checker/defect_classifier.py
def classify_defects(image_bytes: bytes) -> dict:
    landmarks = get_face_mesh(image_bytes)
    defects = []
    if not eyes_open(landmarks):      defects.append("EYES_CLOSED")
    if not ears_visible(landmarks):   defects.append("EARS_OCCLUDED")
    if not face_complete(landmarks):  defects.append("FACE_PARTIALLY_OCCLUDED")
    return {"pass": len(defects) == 0, "defects": defects}
```

### Step 5 — Return result
On any failure, return HTTP 422 with:
```json
{
  "status": "rejected",
  "defect_code": "EYES_CLOSED",
  "message": "Both eyes must be clearly open and visible in the photo.",
  "action": "Please retake the photo in good lighting with your eyes fully open.",
  "reupload_url": "https://www.govca.rw/document/stepIndvdlDocument.sg"
}
```

## Outcome

- Photo quality issues surfaced in under 2 seconds at upload time.
- Applicant sees the exact defect with plain-language guidance.
- Pipeline only advances photos that pass all three checks.
- False-positive rate target: < 3% (good photos rejected incorrectly).

## Defect Codes Reference

| Code | Meaning |
|------|---------|
| `IMAGE_TOO_BLURRY` | Laplacian variance below threshold |
| `IMAGE_TOO_DARK` | Mean brightness below 40 |
| `IMAGE_TOO_BRIGHT` | Mean brightness above 220 |
| `NO_FACE_DETECTED` | MediaPipe found 0 or 2+ faces |
| `EYES_CLOSED` | Eye-open ratio below 0.25 |
| `EARS_OCCLUDED` | Ear landmark confidence below threshold |
| `FACE_PARTIALLY_OCCLUDED` | Contour landmark coverage below 85% |
