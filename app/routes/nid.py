"""
NID Blueprint — update National ID after photo is accepted, or cancel application
"""
from flask import (
    Blueprint, request, session, jsonify,
    render_template, redirect, url_for
)
from app import db
from app.models import User, Application, AuditLog
from app.services.email_service import send_nid_updated_email
from app import METRICS
import re

nid_bp = Blueprint("nid", __name__)
NID_RE = re.compile(r"^\d{16}$")


def _require_login():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return None


# ── NID update page ───────────────────────────────────────────────────────────
@nid_bp.route("/update", methods=["GET"])
def update_page():
    err = _require_login()
    if err:
        return err
    app_ref = request.args.get("app_ref", "")
    user    = User.query.get(session["user_id"])
    app     = Application.query.filter_by(app_ref=app_ref, user_id=user.id).first_or_404()

    if app.status != Application.PHOTO_ACCEPTED:
        return redirect(url_for("upload.upload_page"))

    return render_template("nid/update.html", user=user, application=app)


# ── Confirm NID update ────────────────────────────────────────────────────────
@nid_bp.route("/confirm", methods=["POST"])
def confirm_update():
    err = _require_login()
    if err:
        return jsonify({"status": "error", "message": "Auth required."}), 401

    data    = request.get_json(silent=True) or request.form
    app_ref = (data.get("app_ref") or "").strip()
    new_nid = (data.get("national_id") or "").strip()

    if not NID_RE.match(new_nid):
        return jsonify({"status": "error",
                        "message": "National ID must be exactly 16 digits."}), 400

    user = User.query.get(session["user_id"])
    app  = Application.query.filter_by(app_ref=app_ref, user_id=user.id).first_or_404()

    if app.status != Application.PHOTO_ACCEPTED:
        return jsonify({"status": "error",
                        "message": "Application is not in an accepted state."}), 409

    # Check uniqueness
    conflict = User.query.filter(
        User.national_id == new_nid, User.id != user.id
    ).first()
    if conflict:
        METRICS["nid_updates"].labels(status="conflict").inc()
        return jsonify({"status": "error",
                        "message": "This National ID is already registered to another account."}), 409

    old_nid       = user.national_id
    user.national_id = new_nid
    app.status    = Application.NID_UPDATED
    app.national_id_updated = True

    db.session.add(AuditLog(
        user_id    = user.id,
        action     = "NID_UPDATED",
        detail     = f"NID changed from {old_nid[:4]}****{old_nid[-4:]} to {new_nid[:4]}****{new_nid[-4:]}",
        ip_address = request.remote_addr,
    ))
    db.session.commit()
    session["national_id"] = new_nid

    send_nid_updated_email(
        current_app._get_current_object() if False else _get_app(),
        to          = user.email,
        app_ref     = app_ref,
        full_name   = user.full_name or user.national_id,
        national_id = new_nid,
    )

    METRICS["nid_updates"].labels(status="success").inc()
    return jsonify({
        "status":  "ok",
        "message": "National ID updated successfully. Your application is now complete.",
        "app_ref": app_ref,
        "next":    url_for("upload.upload_page"),
    })


# ── Cancel application ────────────────────────────────────────────────────────
@nid_bp.route("/cancel/<app_ref>", methods=["POST"])
def cancel_application(app_ref: str):
    err = _require_login()
    if err:
        return jsonify({"status": "error", "message": "Auth required."}), 401

    user = User.query.get(session["user_id"])
    app  = Application.query.filter_by(app_ref=app_ref, user_id=user.id).first_or_404()
    app.status = "CANCELLED"

    db.session.add(AuditLog(
        user_id    = user.id,
        action     = "APPLICATION_CANCELLED",
        detail     = f"Application {app_ref} cancelled by user",
        ip_address = request.remote_addr,
    ))
    db.session.commit()

    return jsonify({
        "status":  "ok",
        "message": "Application cancelled. You may start a new application at any time.",
        "restart": url_for("upload.upload_page"),
    })


def _get_app():
    from flask import current_app
    return current_app._get_current_object()
