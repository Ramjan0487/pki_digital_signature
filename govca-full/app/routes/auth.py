"""
Auth Blueprint — mTLS + password login, session management, logout
PKI: client certificate verified by Nginx before request reaches Flask.
Flask then validates the cert DN against the user record.
"""
import re
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import (
    Blueprint, request, session, jsonify,
    render_template, redirect, url_for, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash
from app import db, limiter
from app.models import User, AuditLog
from app import METRICS

auth_bp = Blueprint("auth", __name__)

NID_RE = re.compile(r"^\d{16}$")


# ── Helpers ──────────────────────────────────────────────────────────────────
def _audit(action: str, detail: str, user_id=None):
    db.session.add(AuditLog(
        user_id=user_id,
        action=action,
        detail=detail,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:256],
    ))
    db.session.commit()


def _verify_mtls_cert(user: User) -> tuple[bool, str]:
    """
    Nginx forwards client cert headers after verification:
      X-SSL-Client-Verify: SUCCESS
      X-SSL-Client-DN:     /CN=1199780123456789/O=GovCA/C=RW
      X-SSL-Client-Serial: ABC123...
    """
    if not current_app.config.get("VERIFY_CLIENT_CERT"):
        return True, "mTLS disabled (dev mode)"

    verify_status = request.headers.get("X-SSL-Client-Verify", "NONE")
    if verify_status != "SUCCESS":
        return False, f"Client certificate not verified: {verify_status}"

    client_dn     = request.headers.get("X-SSL-Client-DN", "")
    client_serial = request.headers.get("X-SSL-Client-Serial", "")

    if user.cert_subject and user.cert_subject != client_dn:
        return False, f"Certificate DN mismatch. Expected: {user.cert_subject}"
    if user.cert_serial and user.cert_serial != client_serial:
        return False, "Certificate serial mismatch."

    return True, "OK"


# ── Login page ────────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    data = request.get_json(silent=True) or request.form
    national_id = (data.get("national_id") or "").strip()
    password    = (data.get("password")    or "").strip()

    # ── Input validation ──────────────────────────────────────────────────────
    if not NID_RE.match(national_id):
        METRICS["login_total"].labels(status="invalid_nid").inc()
        return _error(400, "National ID must be exactly 16 digits.")

    if len(password) < 8:
        METRICS["login_total"].labels(status="invalid_password").inc()
        return _error(400, "Password must be at least 8 characters.")

    # ── Lookup user ───────────────────────────────────────────────────────────
    user = User.query.filter_by(national_id=national_id).first()
    if not user:
        METRICS["login_total"].labels(status="not_found").inc()
        _audit("LOGIN_FAIL", f"NID {national_id} not found")
        return _error(401, "Incorrect National ID or password.")

    # ── Account lock check ────────────────────────────────────────────────────
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60)
        METRICS["login_total"].labels(status="locked").inc()
        return _error(423, f"Account locked for {remaining} more minutes. Contact GovCA helpdesk.")

    # ── Password check ────────────────────────────────────────────────────────
    if not check_password_hash(user.password_hash, password):
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=30)
            _audit("ACCOUNT_LOCKED", f"NID {national_id} locked after 5 failed attempts", user.id)
        db.session.commit()
        METRICS["login_total"].labels(status="wrong_password").inc()
        _audit("LOGIN_FAIL", f"Wrong password for NID {national_id}", user.id)
        return _error(401, "Incorrect National ID or password.")

    # ── mTLS certificate verification ─────────────────────────────────────────
    cert_ok, cert_msg = _verify_mtls_cert(user)
    if not cert_ok:
        METRICS["login_total"].labels(status="cert_fail").inc()
        _audit("MTLS_FAIL", cert_msg, user.id)
        return _error(401, f"Client certificate error: {cert_msg}")

    # ── Success ───────────────────────────────────────────────────────────────
    user.failed_logins = 0
    user.locked_until  = None
    db.session.commit()

    session.permanent = True
    session["user_id"]    = user.id
    session["national_id"] = user.national_id
    session["csrf_token"] = secrets.token_hex(32)

    METRICS["login_total"].labels(status="success").inc()
    METRICS["active_sessions"].inc()
    _audit("LOGIN_SUCCESS", f"NID {national_id}", user.id)

    return jsonify({
        "status":     "ok",
        "message":    "Login successful.",
        "csrf_token": session["csrf_token"],
        "redirect":   url_for("upload.upload_page"),
    })


# ── Logout ────────────────────────────────────────────────────────────────────
@auth_bp.route("/logout", methods=["POST"])
def logout():
    user_id = session.get("user_id")
    session.clear()
    METRICS["active_sessions"].dec()
    _audit("LOGOUT", "User logged out", user_id)
    return redirect(url_for("auth.login"))


# ── Register (dev/admin only) ─────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per hour")
def register():
    data = request.get_json(silent=True) or {}
    national_id = (data.get("national_id") or "").strip()
    email       = (data.get("email")       or "").strip()
    password    = (data.get("password")    or "").strip()
    full_name   = (data.get("full_name")   or "").strip()

    if not NID_RE.match(national_id):
        return _error(400, "National ID must be exactly 16 digits.")
    if "@" not in email:
        return _error(400, "Invalid email address.")
    if len(password) < 8:
        return _error(400, "Password too short (min 8 characters).")

    if User.query.filter_by(national_id=national_id).first():
        return _error(409, "An account with this National ID already exists.")

    user = User(
        national_id   = national_id,
        email         = email,
        password_hash = generate_password_hash(password),
        full_name     = full_name,
    )
    db.session.add(user)
    db.session.commit()
    _audit("REGISTER", f"New user NID {national_id}", user.id)
    return jsonify({"status": "ok", "message": "Account created."})


# ── Helpers ───────────────────────────────────────────────────────────────────
def _error(code: int, message: str):
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"status": "error", "message": message,
                        "forgot_url": url_for("auth.login")}), code
    return render_template("auth/login.html", error=message), code
