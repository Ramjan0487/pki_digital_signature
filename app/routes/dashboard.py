"""
TestOps Dashboard Blueprint — live metrics, test results, system health
Exposes: /dashboard/ (HTML), /dashboard/api/metrics (JSON), /dashboard/api/health
"""
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, render_template, session, redirect, url_for
from sqlalchemy import func
from app import db
from app.models import User, Application, ImageCheck, AuditLog

dash_bp = Blueprint("dashboard", __name__)


def _admin_required():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return None


# ── Dashboard HTML ────────────────────────────────────────────────────────────
@dash_bp.route("/")
def index():
    err = _admin_required()
    if err:
        return err
    return render_template("dashboard/index.html")


# ── Live metrics API ──────────────────────────────────────────────────────────
@dash_bp.route("/api/metrics")
def metrics_api():
    now   = datetime.utcnow()
    h24   = now - timedelta(hours=24)
    h1    = now - timedelta(hours=1)

    # Uploads last 24h
    total_24h   = ImageCheck.query.filter(ImageCheck.checked_at >= h24).count()
    accepted_24h= ImageCheck.query.filter(
        ImageCheck.checked_at >= h24, ImageCheck.result == "ACCEPTED").count()
    rejected_24h= total_24h - accepted_24h

    # Last hour
    total_1h    = ImageCheck.query.filter(ImageCheck.checked_at >= h1).count()

    # Average detection time (ms)
    avg_ms_row  = db.session.query(func.avg(ImageCheck.duration_ms))\
                            .filter(ImageCheck.checked_at >= h24).scalar()
    avg_ms      = round(float(avg_ms_row or 0), 1)

    # Defect breakdown
    defects = db.session.query(
        ImageCheck.defect_code, func.count(ImageCheck.id).label("cnt")
    ).filter(
        ImageCheck.checked_at >= h24,
        ImageCheck.result == "REJECTED"
    ).group_by(ImageCheck.defect_code).all()

    # Active users
    active_sessions = User.query.filter(
        User.is_active == True
    ).count()

    # NID updates
    nid_updates_24h = Application.query.filter(
        Application.updated_at >= h24,
        Application.status == "NID_UPDATED"
    ).count()

    # Login events
    logins_24h = AuditLog.query.filter(
        AuditLog.timestamp >= h24,
        AuditLog.action == "LOGIN_SUCCESS"
    ).count()
    login_fails_24h = AuditLog.query.filter(
        AuditLog.timestamp >= h24,
        AuditLog.action == "LOGIN_FAIL"
    ).count()

    # Hourly trend (last 12 hours)
    trend = []
    for i in range(11, -1, -1):
        slot_start = now - timedelta(hours=i+1)
        slot_end   = now - timedelta(hours=i)
        cnt = ImageCheck.query.filter(
            ImageCheck.checked_at >= slot_start,
            ImageCheck.checked_at < slot_end
        ).count()
        trend.append({
            "hour":  slot_start.strftime("%H:%M"),
            "count": cnt,
        })

    return jsonify({
        "timestamp":       now.isoformat() + "Z",
        "uploads_24h":     total_24h,
        "uploads_1h":      total_1h,
        "accepted_24h":    accepted_24h,
        "rejected_24h":    rejected_24h,
        "accept_rate":     round(accepted_24h / total_24h * 100, 1) if total_24h else 0,
        "avg_detect_ms":   avg_ms,
        "nid_updates_24h": nid_updates_24h,
        "logins_24h":      logins_24h,
        "login_fails_24h": login_fails_24h,
        "active_users":    active_sessions,
        "defect_breakdown":[{"code": d.defect_code, "count": d.cnt} for d in defects],
        "hourly_trend":    trend,
    })


# ── Health check ──────────────────────────────────────────────────────────────
@dash_bp.route("/api/health")
def health():
    checks = {}

    # Database
    try:
        db.session.execute(db.text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}

    # MediaPipe
    try:
        import mediapipe  # noqa
        checks["mediapipe"] = {"status": "ok", "version": mediapipe.__version__}
    except ImportError:
        checks["mediapipe"] = {"status": "error", "detail": "Not installed"}

    # OpenCV
    try:
        import cv2
        checks["opencv"] = {"status": "ok", "version": cv2.__version__}
    except ImportError:
        checks["opencv"] = {"status": "error", "detail": "Not installed"}

    overall = "ok" if all(c["status"] == "ok" for c in checks.values()) else "degraded"
    return jsonify({
        "status":    overall,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks":    checks,
    }), 200 if overall == "ok" else 503


# ── Recent activity feed ──────────────────────────────────────────────────────
@dash_bp.route("/api/activity")
def activity():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(50).all()
    return jsonify([{
        "action":    l.action,
        "detail":    l.detail,
        "ip":        l.ip_address,
        "timestamp": l.timestamp.isoformat() + "Z",
    } for l in logs])
