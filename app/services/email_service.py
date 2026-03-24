"""
Email notification service — Celery task + Flask-Mail fallback
Templates: image_rejected.html, image_accepted.html, nid_updated.html
"""
import os
from celery import Celery
from flask import current_app, render_template
from flask_mail import Message
from app import mail, METRICS

celery_app = Celery(
    "govca",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
)


DEFECT_LABELS = {
    "IMAGE_TOO_BLURRY":    "Photo is too blurry",
    "IMAGE_TOO_DARK":      "Photo is too dark",
    "IMAGE_TOO_BRIGHT":    "Photo is overexposed",
    "LOW_CONTRAST":        "Photo has very low contrast",
    "IMAGE_TOO_SMALL":     "Photo resolution too low",
    "INVALID_IMAGE":       "File is not a valid image",
    "NO_FACE_DETECTED":    "No face detected",
    "MULTIPLE_FACES":      "Multiple faces detected",
    "FACE_TOO_SMALL":      "Face too small in frame",
    "EYES_CLOSED":         "Both eyes closed",
    "LEFT_EYE_CLOSED":     "Left eye closed or obscured",
    "RIGHT_EYE_CLOSED":    "Right eye closed or obscured",
    "LEFT_EAR_OCCLUDED":   "Left ear not visible",
    "RIGHT_EAR_OCCLUDED":  "Right ear not visible",
    "FACE_OCCLUDED":       "Face partially covered or out of frame",
}


def send_rejection_email(app, to: str, app_ref: str,
                          defect_code: str, defect_message: str):
    """Send image-rejection notification (inline for sync context)."""
    with app.app_context():
        defect_label = DEFECT_LABELS.get(defect_code, "Photo issue detected")
        html = _render("email/image_rejected.html", {
            "app_ref":       app_ref,
            "defect_label":  defect_label,
            "defect_message": defect_message,
            "defect_code":   defect_code,
            "reupload_url":  f"https://www.govca.rw/document/stepIndvdlDocument.sg?app={app_ref}",
            "cancel_url":    f"https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg?id={app_ref}",
        })
        _send(to, f"[GovCA] Action required — Application {app_ref}", html)
        METRICS["email_sent"].labels(type="rejection").inc()


def send_acceptance_email(app, to: str, app_ref: str, full_name: str):
    """Send image-accepted / proceed to NID update notification."""
    with app.app_context():
        html = _render("email/image_accepted.html", {
            "app_ref":   app_ref,
            "full_name": full_name,
            "nid_url":   f"https://www.govca.rw/nid/update?app={app_ref}",
        })
        _send(to, f"[GovCA] Photo accepted — Update your National ID ({app_ref})", html)
        METRICS["email_sent"].labels(type="accepted").inc()


def send_nid_updated_email(app, to: str, app_ref: str, full_name: str, national_id: str):
    """Confirm National ID record update."""
    with app.app_context():
        masked_nid = national_id[:4] + "********" + national_id[-4:]
        html = _render("email/nid_updated.html", {
            "app_ref":    app_ref,
            "full_name":  full_name,
            "masked_nid": masked_nid,
            "status_url": f"https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg?id={app_ref}",
        })
        _send(to, f"[GovCA] National ID updated — Application {app_ref}", html)
        METRICS["email_sent"].labels(type="nid_updated").inc()


# ── Internal helpers ──────────────────────────────────────────────────────────
def _render(template: str, ctx: dict) -> str:
    try:
        return render_template(template, **ctx)
    except Exception:
        return _fallback_html(ctx)


def _send(to: str, subject: str, html: str):
    try:
        msg = Message(subject=subject, recipients=[to], html=html)
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Email send failed to {to}: {e}")


def _fallback_html(ctx: dict) -> str:
    """Minimal plain-HTML fallback if template rendering fails."""
    return f"""
    <html><body>
    <h2>GovCA Portal Notification</h2>
    <p>Application: <strong>{ctx.get('app_ref','N/A')}</strong></p>
    <p>{ctx.get('defect_message', ctx.get('full_name', ''))}</p>
    <p>Visit <a href="https://www.govca.rw">www.govca.rw</a> for details.</p>
    </body></html>
    """
