"""
API routes — image validation + login
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from src.image_checker.clarity import check_clarity
from src.image_checker.face_detector import detect_face
from src.image_checker.defect_classifier import classify_defects
from src.email_service.mailer import send_image_problem_email
from src.auth.login import authenticate_user

router = APIRouter()

GOVCA_DOCUMENT_URL = "https://www.govca.rw/document/stepIndvdlDocument.sg"
GOVCA_STATUS_URL   = "https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg"

# ── UC-01: Login ──────────────────────────────────────────────────────────────
@router.post("/login")
async def login(national_id: str = Form(...), password: str = Form(...)):
    result = authenticate_user(national_id, password)
    if result["success"]:
        return {"status": "ok", "session_token": result["token"]}
    raise HTTPException(status_code=401, detail=result["error"])


# ── UC-02 + UC-03: Image validation + email ───────────────────────────────────
@router.post("/validate-image")
async def validate_image(
    file: UploadFile = File(...),
    application_id: str = Form(...),
    user_email: str = Form(...),
):
    image_bytes = await file.read()

    # Check 1: Clarity
    clarity = check_clarity(image_bytes)
    if not clarity["pass"]:
        _notify(user_email, application_id, clarity["defect"], clarity["message"])
        return JSONResponse(status_code=422, content=_rejection(clarity))

    # Check 2: Face presence
    face = detect_face(image_bytes)
    if not face["pass"]:
        _notify(user_email, application_id, face["defect"], face["message"])
        return JSONResponse(status_code=422, content=_rejection(face))

    # Check 3: Landmark defects (eyes, ears, occlusion)
    defects = classify_defects(image_bytes)
    if not defects["pass"]:
        primary = defects["defects"][0]
        _notify(user_email, application_id, primary, defects["message"])
        return JSONResponse(status_code=422, content=_rejection(defects))

    return {"status": "accepted", "application_id": application_id}


def _rejection(result: dict) -> dict:
    return {
        "status": "rejected",
        "defect_code": result.get("defect") or result.get("defects", ["UNKNOWN"])[0],
        "message": result.get("message", "Your photo could not be accepted."),
        "action": "Please retake your photo and upload again.",
        "reupload_url": GOVCA_DOCUMENT_URL,
    }


def _notify(email: str, app_id: str, defect: str, message: str):
    """Fire-and-forget email notification (UC-03)."""
    try:
        send_image_problem_email.delay(
            to=email,
            application_id=app_id,
            defect_code=defect,
            message=message,
            reupload_url=f"{GOVCA_DOCUMENT_URL}?app={app_id}",
            cancel_url=f"{GOVCA_STATUS_URL}?id={app_id}",
        )
    except Exception:
        pass  # email failure must not block the HTTP response
