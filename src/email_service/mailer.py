"""
UC-03 · Email notification service (Celery task)
Sends structured HTML email when an image is rejected.
"""
import smtplib
import ssl
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from celery import Celery

celery_app = Celery(
    "govca",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.govca.rw")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER     = os.getenv("SMTP_USER", "noreply@govca.rw")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_ADDRESS  = "GovCA Portal <noreply@govca.rw>"

DEFECT_DESCRIPTIONS = {
    "IMAGE_TOO_BLURRY":         "Your photo is too blurry.",
    "IMAGE_TOO_DARK":           "Your photo is too dark.",
    "IMAGE_TOO_BRIGHT":         "Your photo is overexposed.",
    "LOW_CONTRAST":             "Your photo has very low contrast.",
    "IMAGE_TOO_SMALL":          "Your photo resolution is too low.",
    "INVALID_IMAGE":            "The uploaded file is not a valid image.",
    "NO_FACE_DETECTED":         "No face was detected in the photo.",
    "MULTIPLE_FACES_DETECTED":  "More than one face was detected.",
    "FACE_TOO_SMALL":           "Your face is too small in the frame.",
    "EYES_CLOSED":              "Both eyes appear closed.",
    "LEFT_EYE_CLOSED":          "Your left eye appears closed or obscured.",
    "RIGHT_EYE_CLOSED":         "Your right eye appears closed or obscured.",
    "LEFT_EAR_OCCLUDED":        "Your left ear is not visible.",
    "RIGHT_EAR_OCCLUDED":       "Your right ear is not visible.",
    "FACE_PARTIALLY_OCCLUDED":  "Part of your face is covered or out of frame.",
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_image_problem_email(
    self,
    to: str,
    application_id: str,
    defect_code: str,
    message: str,
    reupload_url: str,
    cancel_url: str,
):
    """Celery task: send rejection notification email."""
    defect_label = DEFECT_DESCRIPTIONS.get(defect_code, "An issue was found with your photo.")
    html = _build_html(application_id, defect_code, defect_label, message, reupload_url, cancel_url)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[GovCA] Action required — Application {application_id}"
    msg["From"]    = FROM_ADDRESS
    msg["To"]      = to
    msg.attach(MIMEText(_build_plain(application_id, defect_label, message, reupload_url), "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to, msg.as_string())
    except Exception as exc:
        raise self.retry(exc=exc)


def _build_plain(app_id, defect_label, message, reupload_url):
    return f"""
GovCA — Digital Certificate Application: {app_id}

Your photo could not be accepted.

Problem: {defect_label}
Details: {message}

To fix this, please upload a new photo:
{reupload_url}

Photo requirements:
- Clear and in focus
- Face fully visible, eyes open
- Plain light-coloured background
- No sunglasses, hats, or masks
- Minimum 300 x 300 pixels

If you need help, contact GovCA:
Phone: +250 788 315 861
Email: info@govca.rw
Website: https://www.govca.rw
"""


def _build_html(app_id, defect_code, defect_label, message, reupload_url, cancel_url):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GovCA — Photo Issue</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
  .wrap {{ max-width: 600px; margin: 32px auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .header {{ background: #004b87; padding: 24px 32px; }}
  .header h1 {{ color: #fff; margin: 0; font-size: 20px; }}
  .header p {{ color: #cde; margin: 4px 0 0; font-size: 13px; }}
  .body {{ padding: 32px; color: #333; line-height: 1.6; }}
  .alert {{ background: #fff3cd; border-left: 4px solid #f0ad4e; padding: 14px 18px; border-radius: 4px; margin-bottom: 24px; }}
  .alert strong {{ color: #856404; }}
  .alert p {{ margin: 6px 0 0; color: #664d03; font-size: 14px; }}
  .defect-code {{ font-family: monospace; font-size: 12px; color: #888; }}
  .requirements {{ background: #f8f9fa; border-radius: 6px; padding: 16px 20px; margin: 20px 0; }}
  .requirements h3 {{ margin: 0 0 10px; font-size: 14px; color: #555; }}
  .requirements ul {{ margin: 0; padding-left: 20px; font-size: 14px; color: #444; }}
  .btn-primary {{ display: inline-block; background: #004b87; color: #fff !important; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: bold; font-size: 15px; margin-right: 12px; }}
  .btn-secondary {{ display: inline-block; color: #666 !important; text-decoration: underline; font-size: 13px; padding: 14px 0; }}
  .footer {{ background: #f5f5f5; padding: 20px 32px; font-size: 12px; color: #888; border-top: 1px solid #eee; }}
  .footer a {{ color: #004b87; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>Rwanda National Digital Certification Center</h1>
    <p>Application ID: {app_id}</p>
  </div>
  <div class="body">
    <p>Dear Applicant,</p>
    <p>We were unable to accept the photo you submitted for your digital certificate application. Please review the issue below and upload a new photo to continue.</p>

    <div class="alert">
      <strong>Photo issue: {defect_label}</strong>
      <p>{message}</p>
      <span class="defect-code">Code: {defect_code}</span>
    </div>

    <div class="requirements">
      <h3>Photo requirements</h3>
      <ul>
        <li>Clear and in focus — not blurry</li>
        <li>Good lighting — not too dark or overexposed</li>
        <li>Full face visible — eyes open, both ears partially visible</li>
        <li>Plain light-coloured background</li>
        <li>No sunglasses, hats, scarves, or masks</li>
        <li>Minimum 300 × 300 pixels</li>
      </ul>
    </div>

    <p>
      <a class="btn-primary" href="{reupload_url}">Change Photo</a>
      <a class="btn-secondary" href="{cancel_url}">Do not continue</a>
    </p>

    <p style="font-size:13px;color:#888;margin-top:28px;">
      If you did not submit this application, please contact us immediately at
      <a href="mailto:info@govca.rw">info@govca.rw</a>.
    </p>
  </div>
  <div class="footer">
    <strong>GovCA — Rwanda National Digital Certification Center</strong><br>
    Phone: +250 788 315 861 &nbsp;|&nbsp; Email: <a href="mailto:info@govca.rw">info@govca.rw</a><br>
    <a href="https://www.govca.rw">www.govca.rw</a> &nbsp;|&nbsp;
    <a href="https://www.govca.rw/about/contacts.sg">Contact Us</a>
  </div>
</div>
</body>
</html>"""
