# UC-03 · Email Notification & User Decision

## Problem

When an image fails validation (UC-02), the applicant currently receives no asynchronous notification. They must:

- Return to the portal and check application status manually at `/indvdl/applyDetails/form/applyInfo.sg`.
- Guess what went wrong — the error message (if any) is generic.
- Navigate back to the document upload step themselves.

Many applicants abandon the process at this point, believing the application was lost or that they need to start over. Others resubmit the same flawed photo, wasting both their time and GovCA officer time.

## Solution

A Celery-backed email notification service that:

1. Fires within 60 seconds of a UC-02 rejection.
2. Sends a structured HTML email to the applicant's registered address.
3. Email content includes: the exact defect code in plain language, a visual guide (what a valid photo looks like), a one-click re-upload link, and the application reference number.
4. Email contains two clear calls to action: **Change Photo** (link to `/document/stepIndvdlDocument.sg`) and **Cancel Application** (link to abandon flow).
5. If the user takes no action within 72 hours, a reminder email is sent once.

## How To

### Step 1 — Trigger notification task
On UC-02 rejection, the API enqueues a Celery task:
```python
# src/api/routes.py
from src.email_service.mailer import send_image_problem_email

@router.post("/validate-image")
async def validate_image(file: UploadFile, application_id: str, user_email: str):
    result = run_image_checks(await file.read())
    if not result["pass"]:
        send_image_problem_email.delay(
            to=user_email,
            application_id=application_id,
            defect_code=result["defect_code"],
            message=result["message"],
            reupload_url="https://www.govca.rw/document/stepIndvdlDocument.sg"
        )
        return JSONResponse(status_code=422, content=result)
    return {"status": "accepted"}
```

### Step 2 — Celery task sends email
```python
# src/email_service/mailer.py
from celery import Celery
from jinja2 import Environment, FileSystemLoader
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

app = Celery("govca", broker="redis://localhost:6379/0")

@app.task
def send_image_problem_email(to, application_id, defect_code, message, reupload_url):
    env = Environment(loader=FileSystemLoader("src/email_service/templates"))
    template = env.get_template("image_problem.html")
    html = template.render(
        application_id=application_id,
        defect_code=defect_code,
        message=message,
        reupload_url=reupload_url,
        cancel_url=f"https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg?id={application_id}"
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[GovCA] Action required on application {application_id}"
    msg["From"] = "noreply@govca.rw"
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.govca.rw", 465, context=context) as server:
        server.login("noreply@govca.rw", SMTP_PASSWORD)
        server.sendmail("noreply@govca.rw", to, msg.as_string())
```

### Step 3 — User receives email and decides
The email presents two buttons:

- **Change Photo** → `https://www.govca.rw/document/stepIndvdlDocument.sg?app={application_id}`  
  Brings the user directly back to the upload step with the application pre-loaded.

- **Do Not Continue** → `https://www.govca.rw/indvdl/applyDetails/form/applyInfo.sg?id={application_id}`  
  Shows the application status page; no further action is taken.

### Step 4 — Reminder (72-hour follow-up)
```python
# Celery beat schedule in config/settings.py
CELERY_BEAT_SCHEDULE = {
    "reminder-72h": {
        "task": "src.email_service.mailer.send_reminder_email",
        "schedule": crontab(hour=0, minute=0),
    }
}
```

## Outcome

- 100% of UC-02 rejections trigger an email within 60 seconds.
- Email open rate target: > 70% (subject line includes application number).
- Re-upload rate (users who act on the email): target > 55%.
- Applicants who abandon can do so cleanly without leaving orphaned applications.

## Email Content Specification

| Field | Value |
|-------|-------|
| From | noreply@govca.rw |
| Subject | `[GovCA] Action required on application {APP-ID}` |
| Language | English (ENG) or Kinyarwanda (KNY) based on portal language setting |
| Defect section | Plain-language description of what was wrong |
| Photo guide | Inline image: correct vs incorrect photo examples |
| CTA 1 | "Change Photo" button — links to `/document/stepIndvdlDocument.sg` |
| CTA 2 | "Do Not Continue" link — links to `/indvdl/applyDetails/form/applyInfo.sg` |
| Footer | GovCA contact: +250 788 315 861 · info@govca.rw |
