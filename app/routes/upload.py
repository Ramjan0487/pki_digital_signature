"""
Upload Blueprint — image upload → AI detection → accept/reject → NID flow
"""
import uuid
import time
import base64
from flask import (
    Blueprint, request, session, jsonify,
    render_template, redirect, url_for, current_app
)
from werkzeug.utils import secure_filename
from app import db, limiter
from app.models import User, Application, ImageCheck, AuditLog
from app.services.face_detection import FaceDetector
from app.services.email_service import send_rejection_email, send_acceptance_email
from app import METRICS

upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "webp"}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _require_login():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Authentication required."}), 401
    return None


# ── Upload page ───────────────────────────────────────────────────────────────
@upload_bp.route("/", methods=["GET"])
def upload_page():
    err = _require_login()
    if err:
        return redirect(url_for("auth.login"))
    user = User.query.get(session["user_id"])
    apps = Application.query.filter_by(user_id=user.id)\
                            .order_by(Application.submitted_at.desc()).all()
    return render_template("upload/upload.html", user=user, applications=apps)


# ── Submit photo ──────────────────────────────────────────────────────────────
@upload_bp.route("/submit", methods=["POST"])
@limiter.limit("20 per hour")
def submit():
    err = _require_login()
    if err:
        return err

    user = User.query.get(session["user_id"])

    # ── Validate file ─────────────────────────────────────────────────────────
    if "photo" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded."}), 400

    photo = request.files["photo"]
    if not photo.filename or not _allowed(photo.filename):
        return jsonify({"status": "error",
                        "message": "Invalid file type. Upload a JPG, PNG, BMP, or WebP image."}), 400

    max_bytes = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    image_bytes = photo.read(max_bytes + 1)
    if len(image_bytes) > max_bytes:
        return jsonify({"status": "error",
                        "message": f"File too large. Maximum size is {current_app.config['MAX_UPLOAD_MB']} MB."}), 413

    # ── Get or create application ─────────────────────────────────────────────
    app_ref = request.form.get("app_ref") or f"APP-{uuid.uuid4().hex[:12].upper()}"
    application = Application.query.filter_by(app_ref=app_ref, user_id=user.id).first()
    if not application:
        cert_type   = request.form.get("cert_type", "LOCAL_INDIVIDUAL")
        application = Application(app_ref=app_ref, user_id=user.id, cert_type=cert_type)
        db.session.add(application)

    application.photo_attempts += 1
    application.status = Application.PENDING_PHOTO

    # ── Run AI detection ──────────────────────────────────────────────────────
    cfg = {k: current_app.config[k] for k in [
        "BLUR_THRESHOLD","MIN_BRIGHTNESS","MAX_BRIGHTNESS",
        "EYE_OPEN_RATIO","EAR_EDGE_MARGIN","FACE_MIN_COVERAGE","FACE_CONFIDENCE"
    ]}
    detector = FaceDetector(cfg)

    with METRICS["detection_duration"].time():
        result = detector.detect(image_bytes)

    METRICS["upload_total"].labels(result="accepted" if result.passed else "rejected").inc()

    # ── Persist check record ──────────────────────────────────────────────────
    check = ImageCheck(
        application_id  = application.id if application.id else None,
        filename        = secure_filename(photo.filename),
        result          = "ACCEPTED" if result.passed else "REJECTED",
        defect_code     = result.defect_code,
        defect_message  = result.defect_message,
        blur_score      = result.blur_score,
        brightness      = result.brightness,
        face_confidence = result.face_confidence,
        eye_ratio_left  = result.eye_ratio_left,
        eye_ratio_right = result.eye_ratio_right,
        face_coverage   = result.face_coverage,
        duration_ms     = result.duration_ms,
    )

    if result.passed:
        application.status = Application.PHOTO_ACCEPTED
        db.session.add(check)
        db.session.commit()
        check.application_id = application.id
        db.session.commit()

        send_acceptance_email(
            current_app._get_current_object(),
            to        = user.email,
            app_ref   = app_ref,
            full_name = user.full_name or user.national_id,
        )

        annotated_b64 = (base64.b64encode(result.annotated_img).decode()
                         if result.annotated_img else None)
        return jsonify({
            "status":        "accepted",
            "app_ref":       app_ref,
            "message":       "Photo accepted! Please proceed to update your National ID.",
            "annotated_img": annotated_b64,
            "scores": {
                "blur":          result.blur_score,
                "brightness":    result.brightness,
                "face_conf":     result.face_confidence,
                "eye_left":      result.eye_ratio_left,
                "eye_right":     result.eye_ratio_right,
                "face_coverage": result.face_coverage,
                "duration_ms":   result.duration_ms,
            },
            "next": url_for("nid.update_page", app_ref=app_ref),
        })

    else:
        application.status = Application.PHOTO_REJECTED
        db.session.add(check)
        db.session.commit()
        check.application_id = application.id
        db.session.commit()

        send_rejection_email(
            current_app._get_current_object(),
            to             = user.email,
            app_ref        = app_ref,
            defect_code    = result.defect_code,
            defect_message = result.defect_message,
        )

        return jsonify({
            "status":      "rejected",
            "app_ref":     app_ref,
            "defect_code": result.defect_code,
            "message":     result.defect_message,
            "action":      "Please retake your photo and try again, or cancel this application.",
            "scores": {
                "blur":       result.blur_score,
                "brightness": result.brightness,
                "duration_ms": result.duration_ms,
            },
            "options": {
                "retry":  url_for("upload.upload_page"),
                "cancel": url_for("nid.cancel_application", app_ref=app_ref),
            },
        }), 422


# ── Get application status ────────────────────────────────────────────────────
@upload_bp.route("/status/<app_ref>", methods=["GET"])
def status(app_ref: str):
    err = _require_login()
    if err:
        return err
    app = Application.query.filter_by(
        app_ref=app_ref, user_id=session["user_id"]
    ).first_or_404()
    checks = app.checks.order_by(ImageCheck.checked_at.desc()).all()
    return jsonify({
        "app_ref":       app.app_ref,
        "status":        app.status,
        "cert_type":     app.cert_type,
        "photo_attempts":app.photo_attempts,
        "nid_updated":   app.national_id_updated,
        "checks":        [c.result + " — " + (c.defect_code or "OK") for c in checks],
    })
