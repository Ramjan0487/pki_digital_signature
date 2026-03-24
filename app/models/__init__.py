"""SQLAlchemy models — User, Application, ImageCheck, AuditLog"""
from datetime import datetime
from app import db


class User(db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    national_id   = db.Column(db.String(16), unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name     = db.Column(db.String(120))
    cert_subject  = db.Column(db.String(256))      # mTLS client cert DN
    cert_serial   = db.Column(db.String(64))       # mTLS cert serial
    is_active     = db.Column(db.Boolean, default=True)
    failed_logins = db.Column(db.Integer, default=0)
    locked_until  = db.Column(db.DateTime, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applications  = db.relationship("Application", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User NID={self.national_id}>"


class Application(db.Model):
    __tablename__ = "applications"
    id             = db.Column(db.Integer, primary_key=True)
    app_ref        = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    cert_type      = db.Column(db.String(32))      # LOCAL_INDIVIDUAL, COMPANY, etc.
    status         = db.Column(db.String(32), default="PENDING_PHOTO")
    national_id_updated = db.Column(db.Boolean, default=False)
    photo_attempts = db.Column(db.Integer, default=0)
    submitted_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user           = db.relationship("User", back_populates="applications")
    checks         = db.relationship("ImageCheck", back_populates="application", lazy="dynamic")

    # Status constants
    PENDING_PHOTO  = "PENDING_PHOTO"
    PHOTO_REJECTED = "PHOTO_REJECTED"
    PHOTO_ACCEPTED = "PHOTO_ACCEPTED"
    NID_UPDATED    = "NID_UPDATED"
    COMPLETE       = "COMPLETE"

    def __repr__(self):
        return f"<Application ref={self.app_ref} status={self.status}>"


class ImageCheck(db.Model):
    __tablename__ = "image_checks"
    id              = db.Column(db.Integer, primary_key=True)
    application_id  = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False)
    filename        = db.Column(db.String(256))
    result          = db.Column(db.String(16))     # ACCEPTED / REJECTED
    defect_code     = db.Column(db.String(64))
    defect_message  = db.Column(db.Text)
    blur_score      = db.Column(db.Float)
    brightness      = db.Column(db.Float)
    face_confidence = db.Column(db.Float)
    eye_ratio_left  = db.Column(db.Float)
    eye_ratio_right = db.Column(db.Float)
    face_coverage   = db.Column(db.Float)
    duration_ms     = db.Column(db.Float)
    checked_at      = db.Column(db.DateTime, default=datetime.utcnow)

    application     = db.relationship("Application", back_populates="checks")

    def __repr__(self):
        return f"<ImageCheck result={self.result} defect={self.defect_code}>"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action     = db.Column(db.String(64), nullable=False)
    detail     = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(256))
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog action={self.action} at={self.timestamp}>"
