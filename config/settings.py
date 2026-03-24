"""
Centralised settings — reads from environment / .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv("config/.env")

REDIS_URL     = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.govca.rw")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER     = os.getenv("SMTP_USER", "noreply@govca.rw")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
GOVCA_AUTH_URL = os.getenv("GOVCA_AUTH_URL", "https://www.govca.rw/auth/api/login")
PORT          = int(os.getenv("PORT", "8000"))
ENVIRONMENT   = os.getenv("ENVIRONMENT", "development")

# Image validation thresholds
BLUR_THRESHOLD   = float(os.getenv("BLUR_THRESHOLD", "80"))
MIN_BRIGHTNESS   = float(os.getenv("MIN_BRIGHTNESS", "40"))
MAX_BRIGHTNESS   = float(os.getenv("MAX_BRIGHTNESS", "220"))

# Celery beat — reminder email after 72h of no action
CELERY_BEAT_SCHEDULE = {
    "send-72h-reminders": {
        "task": "src.email_service.mailer.send_reminder_email",
        "schedule": 3600.0,   # check every hour
    }
}
