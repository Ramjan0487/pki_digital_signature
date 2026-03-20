"""App configuration — Development / Production / Testing"""
import os
from datetime import timedelta


class BaseConfig:
    SECRET_KEY              = os.getenv("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # mTLS
    MTLS_CA_CERT    = os.getenv("MTLS_CA_CERT",    "certs/ca/ca.crt")
    MTLS_SERVER_CERT= os.getenv("MTLS_SERVER_CERT","certs/server/server.crt")
    MTLS_SERVER_KEY = os.getenv("MTLS_SERVER_KEY", "certs/server/server.key")
    VERIFY_CLIENT_CERT = os.getenv("VERIFY_CLIENT_CERT", "true").lower() == "true"

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///govca.db")

    # Mail (SMTP)
    MAIL_SERVER   = os.getenv("MAIL_SERVER",   "smtp.govca.rw")
    MAIL_PORT     = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS  = os.getenv("MAIL_USE_TLS",  "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "noreply@govca.rw")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = ("GovCA Portal", "noreply@govca.rw")

    # OpenCV / MediaPipe thresholds
    BLUR_THRESHOLD    = float(os.getenv("BLUR_THRESHOLD",  "80.0"))
    MIN_BRIGHTNESS    = float(os.getenv("MIN_BRIGHTNESS",  "40.0"))
    MAX_BRIGHTNESS    = float(os.getenv("MAX_BRIGHTNESS",  "220.0"))
    EYE_OPEN_RATIO    = float(os.getenv("EYE_OPEN_RATIO",  "0.22"))
    EAR_EDGE_MARGIN   = float(os.getenv("EAR_EDGE_MARGIN", "0.04"))
    FACE_MIN_COVERAGE = float(os.getenv("FACE_MIN_COVERAGE","0.82"))
    FACE_CONFIDENCE   = float(os.getenv("FACE_CONFIDENCE", "0.70"))
    MAX_UPLOAD_MB     = int(os.getenv("MAX_UPLOAD_MB", "5"))

    # Redis / Celery
    REDIS_URL      = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CELERY_BROKER  = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CELERY_BACKEND = os.getenv("REDIS_URL", "redis://redis:6379/0")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    VERIFY_CLIENT_CERT    = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///govca_dev.db"


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG   = True
    SESSION_COOKIE_SECURE  = False
    VERIFY_CLIENT_CERT     = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MAIL_SUPPRESS_SEND = True
    WTF_CSRF_ENABLED   = False
