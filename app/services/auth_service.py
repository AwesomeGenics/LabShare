"""
app/services/auth_service.py

Business logic for authentication, domain validation, and mock DNS verification.
All external calls (DNS lookup) are mocked behind this interface.
"""

import re
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import abort, current_app, flash, redirect, request, session, url_for
from flask_login import current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import DomainStatus, Institution, InstitutionTier, User, UserRole


# ─────────────────────────────────────────────────────────────────────────────
# Domain validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_email_domain(email: str) -> bool:
    """Return True if email's domain ends with an allowed institutional suffix."""
    allowed = current_app.config.get("ALLOWED_EMAIL_DOMAINS", [".edu", ".ac.in", ".edu.in"])
    email = email.strip().lower()
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1]
    return any(domain.endswith(suffix.lstrip(".")) or ("." + domain).endswith(suffix)
               for suffix in allowed)


def extract_domain(email: str) -> str:
    """Return the domain part of an email address."""
    return email.strip().lower().split("@", 1)[1] if "@" in email else ""


# ─────────────────────────────────────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return generate_password_hash(password)


def check_password(user: User, password: str) -> bool:
    return check_password_hash(user.password_hash, password)


# ─────────────────────────────────────────────────────────────────────────────
# DNS TXT verification (MOCK)
# ─────────────────────────────────────────────────────────────────────────────

def generate_dns_token() -> str:
    """Generate a unique federation token for the institution's DNS TXT record."""
    return f"synapse-fed-token-{secrets.token_hex(16)}"


def mock_dns_verify(institution: Institution) -> dict:
    """
    # MOCK — Simulates a DNS TXT lookup for the institution's verification token.

    In production this would perform an actual DNS TXT query against the
    institution's authoritative nameserver via dnspython or similar.

    Returns:
        dict with keys:
          - success (bool)
          - status  ('verified' | 'pending' | 'not_found')
          - rtt_ms  (simulated round-trip time)
          - message (human-readable)
    """
    import random
    # Simulate a lookup delay
    rtt_ms = random.randint(8, 45)

    # For demo: institutions with verified=True in DB are "found", others are "pending"
    if institution.verified:
        return {
            "success": True,
            "status": "verified",
            "rtt_ms": rtt_ms,
            "message": f"DNS TXT record found and matches token. NS1.{institution.domain.upper()} listening.",
        }

    # Randomly "find" the token 30% of the time for demo variety
    found = random.random() < 0.30
    if found:
        return {
            "success": True,
            "status": "verified",
            "rtt_ms": rtt_ms,
            "message": f"DNS TXT record found and matches token. NS1.{institution.domain.upper()} listening.",
        }

    return {
        "success": False,
        "status": "pending",
        "rtt_ms": rtt_ms,
        "message": f"DNS TXT record not yet detected. Standby: NS1.{institution.domain.upper()} probing.",
    }


def run_dns_verification(institution_id: int) -> dict:
    """
    Trigger mock DNS verification for an institution and update its DB status.
    Returns the mock_dns_verify result dict.
    """
    institution = db.session.get(Institution, institution_id)
    if not institution:
        return {"success": False, "status": "not_found", "message": "Institution not found."}

    result = mock_dns_verify(institution)

    if result["success"] and result["status"] == "verified":
        institution.verified = True
        # Update all users of this institution to verified domain status
        for user in institution.users:
            user.institutional_domain_status = DomainStatus.verified
        db.session.commit()

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

def register_user(
    name: str,
    email: str,
    password: str,
    institution_name: str,
    institution_domain: str,
) -> tuple[User | None, str | None]:
    """
    Create or associate user with an institution.
    Returns (user, error_message). On success error_message is None.
    """
    email = email.strip().lower()
    institution_domain = institution_domain.strip().lower()

    # Domain validation
    if not validate_email_domain(email):
        return None, "Email domain is not an allowed institutional suffix (.edu, .ac.in, etc.)."

    # Duplicate check
    if User.query.filter_by(email=email).first():
        return None, "An account with this email already exists."

    # Find or create institution
    institution = Institution.query.filter_by(domain=institution_domain).first()
    if not institution:
        institution = Institution(
            name=institution_name.strip(),
            domain=institution_domain,
            tier=InstitutionTier.free,
            dns_token=generate_dns_token(),
            verified=False,
        )
        db.session.add(institution)
        db.session.flush()

    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(password),
        role=UserRole.student,
        institution_id=institution.id,
        institutional_domain_status=(
            DomainStatus.verified if institution.verified else DomainStatus.pending
        ),
    )
    db.session.add(user)
    db.session.commit()
    return user, None


# ─────────────────────────────────────────────────────────────────────────────
# RBAC decorators
# ─────────────────────────────────────────────────────────────────────────────

def _effective_role():
    """Return the effective role: DB role always, but session override in DEBUG mode."""
    if current_app.debug:
        override = session.get("_role_override")
        if override:
            return override
    if current_user.is_authenticated:
        return current_user.role.value
    return None


def require_login(f):
    """Redirect to login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """Allow access only to users with one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            role = _effective_role()
            if role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_verified(f):
    """Block access unless the user's institutional domain is verified."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in.", "warning")
            return redirect(url_for("auth.login"))
        if current_user.institutional_domain_status.value != "verified":
            flash("Your institutional domain must be DNS-verified before accessing this feature.", "warning")
            return redirect(url_for("auth.register"))
        return f(*args, **kwargs)
    return decorated
