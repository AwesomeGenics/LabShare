from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required, login_user, logout_user, current_user

from app.extensions import db
from app.models import Institution, User
from app.services.auth_service import (
    check_password,
    register_user,
    run_dns_verification,
    validate_email_domain,
)
from app.services.audit_service import record_event

auth_bp = Blueprint("auth", __name__, template_folder="../../templates/auth")


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("catalog.landing"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and check_password(user, password):
            session.permanent = True
            import secrets
            session["csrf_token"] = secrets.token_hex(32)
            login_user(user, remember=True)
            record_event(
                actor_id=user.id,
                action_type="auth.login",
                ip_address=request.remote_addr,
            )
            next_page = request.args.get("next") or url_for("catalog.landing")
            return redirect(next_page)
        else:
            error = "Invalid email or password."

    return render_template("auth/login.html", error=error)


# ─────────────────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("catalog.landing"))

    email_recognized = False
    institution = None
    error = None
    success = None

    # Pre-check: does email domain look valid?
    prefill_email = request.args.get("email", "")
    if prefill_email:
        email_recognized = validate_email_domain(prefill_email)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        institution_name = request.form.get("institution_name", "").strip()
        institution_domain = request.form.get("institution_domain", "").strip().lower()

        email_recognized = validate_email_domain(email)

        user, err = register_user(name, email, password, institution_name, institution_domain)
        if err:
            error = err
        else:
            institution = user.institution
            record_event(
                actor_id=user.id,
                action_type="auth.register",
                new_state="pending_dns",
                ip_address=request.remote_addr,
            )
            login_user(user)
            success = "Account created! Complete DNS verification below to unlock all features."

    # Fetch institution for dns token display (after POST or if already registered)
    if not institution and current_user.is_authenticated and current_user.institution:
        institution = current_user.institution

    return render_template(
        "auth/register.html",
        error=error,
        success=success,
        email_recognized=email_recognized,
        institution=institution,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DNS Verify (AJAX POST)
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/dns-verify", methods=["POST"])
@login_required
def dns_verify():
    """Trigger mock DNS TXT lookup for the current user's institution."""
    institution_id = current_user.institution_id
    if not institution_id:
        return jsonify({"success": False, "message": "No institution linked to your account."})

    result = run_dns_verification(institution_id)
    record_event(
        actor_id=current_user.id,
        action_type="institution.dns_verify",
        previous_state="pending",
        new_state=result["status"],
        ip_address=request.remote_addr,
    )
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/logout")
def logout():
    if current_user.is_authenticated:
        record_event(
            actor_id=current_user.id,
            action_type="auth.logout",
            ip_address=request.remote_addr,
        )
    logout_user()
    session.pop("_role_override", None)
    flash("You've been signed out.", "success")
    return redirect(url_for("catalog.landing"))


# ─────────────────────────────────────────────────────────────────────────────
# DEBUG role switcher
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/debug-role", methods=["POST"])
def debug_role():
    """DEBUG-only: swap session role override for demo purposes. Never mutates DB."""
    if not current_app.debug:
        abort(404)
    role = request.form.get("role", "").strip()
    if role in ("student", "owner", "admin"):
        session["_role_override"] = role
    else:
        session.pop("_role_override", None)
    return redirect(request.referrer or url_for("catalog.landing"))
