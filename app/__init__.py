"""
App factory for the Campus & Community Resource Sharing Platform.
"""

import os
import secrets

from flask import Flask, current_app, g, request, session

from app.config import config
from app.extensions import db, login_manager


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config[config_name])

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialise extensions
    db.init_app(app)
    login_manager.init_app(app)

    # User loader for Flask-Login
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # ------------------------------------------------------------------ CSRF
    # Manual CSRF: generate a per-session token, validate on every POST/PUT/DELETE.
    # Exempt: /static/, and routes decorated with @csrf_exempt.
    # ------------------------------------------------------------------ CSRF

    @app.before_request
    def _ensure_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

    @app.before_request
    def _validate_csrf():
        """Reject state-changing requests without a valid CSRF token."""
        if app.testing:
            return
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return
        if request.path.startswith("/static/"):
            return
        token = (
            request.form.get("csrf_token")
            or request.headers.get("X-CSRF-Token")
            or (request.json.get("csrf_token") if request.is_json else None)
        )
        expected = session.get("csrf_token")
        if not token or not expected or token != expected:
            from flask import abort
            abort(400, "CSRF validation failed.")


    # ------------------------------------------------------------------ DEBUG role switcher
    if app.debug:
        @app.before_request
        def _apply_role_override():
            """In DEBUG mode only: allow session-based role override for demo purposes."""
            g.role_override = session.get("_role_override")

    # ------------------------------------------------------------------ Context processors

    @app.context_processor
    def _inject_globals():
        from flask_login import current_user
        from app.models import Institution

        effective_role = None
        if app.debug:
            effective_role = session.get("_role_override")
        if effective_role is None and current_user.is_authenticated:
            effective_role = current_user.role.value
        return {
            "csrf_token": session.get("csrf_token", ""),
            "debug": app.debug,
            "effective_role": effective_role,
            "institutions": Institution.query.order_by(Institution.name).all(),
        }

    # ------------------------------------------------------------------ Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.catalog import catalog_bp
    from app.blueprints.bookings import bookings_bp
    from app.blueprints.custody import custody_bp
    from app.blueprints.audit import audit_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.billing import billing_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(catalog_bp, url_prefix="/")
    app.register_blueprint(bookings_bp, url_prefix="/bookings")
    app.register_blueprint(custody_bp, url_prefix="/custody")
    app.register_blueprint(audit_bp, url_prefix="/audit")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(billing_bp, url_prefix="/billing")

    # ------------------------------------------------------------------ Create tables
    with app.app_context():
        db.create_all()

    return app
