"""
GovCA Full-Stack — Application Factory
Covers: mTLS login · AI face detection · Email notification · TestOps dashboard
"""
import os
import ssl
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_client import Counter, Histogram, Gauge, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

db = SQLAlchemy()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)

# ── Prometheus metrics ────────────────────────────────────────────────────────
METRICS = {
    "login_total":        Counter("govca_login_total",        "Total login attempts", ["status"]),
    "upload_total":       Counter("govca_upload_total",       "Total image uploads",  ["result"]),
    "detection_duration": Histogram("govca_detection_seconds", "Face detection latency"),
    "email_sent":         Counter("govca_email_sent_total",   "Emails sent",          ["type"]),
    "active_sessions":    Gauge("govca_active_sessions",      "Active sessions"),
    "nid_updates":        Counter("govca_nid_updates_total",  "National ID updates",  ["status"]),
}


def create_app(config_name: str = "production") -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ── Load config ───────────────────────────────────────────────────────────
    cfg = {
        "development": "app.config.DevelopmentConfig",
        "production":  "app.config.ProductionConfig",
        "testing":     "app.config.TestingConfig",
    }
    app.config.from_object(cfg.get(config_name, cfg["production"]))

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # ── Register blueprints ───────────────────────────────────────────────────
    from app.routes.auth    import auth_bp
    from app.routes.upload  import upload_bp
    from app.routes.nid     import nid_bp
    from app.routes.dashboard import dash_bp

    app.register_blueprint(auth_bp,    url_prefix="/auth")
    app.register_blueprint(upload_bp,  url_prefix="/upload")
    app.register_blueprint(nid_bp,     url_prefix="/nid")
    app.register_blueprint(dash_bp,    url_prefix="/dashboard")

    # ── Mount Prometheus /metrics ──────────────────────────────────────────────
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})

    with app.app_context():
        db.create_all()

    return app
