"""
app/services/audit_service.py

Audit log helper — append-only record_event().
AuditLog rows are NEVER updated or deleted (enforced by SQLAlchemy event listeners).
"""

from datetime import datetime, timezone

from app.extensions import db
from app.models import AuditLog


def record_event(
    actor_id: int,
    action_type: str,
    previous_state: str | None = None,
    new_state: str | None = None,
    resource_id: int | None = None,
    booking_id: int | None = None,
    ip_address: str | None = None,
    notes: str | None = None,
) -> AuditLog:
    """
    Insert a single immutable audit event row.
    Call this from every service that changes state.
    """
    log = AuditLog(
        actor_id=actor_id,
        action_type=action_type,
        previous_state=str(previous_state) if previous_state is not None else None,
        new_state=str(new_state) if new_state is not None else None,
        resource_id=resource_id,
        booking_id=booking_id,
        ip_address=ip_address,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(log)
    # Flush (not commit) so the caller can commit the full transaction atomically
    db.session.flush()
    return log


AUDIT_ACTION_LABELS = {
    "admin.institution_verified": "Institution verified",
    "admin.tier_change": "Institution plan changed",
    "auth.login": "Signed in",
    "auth.logout": "Signed out",
    "auth.register": "Account created",
    "booking.approved": "Booking approved",
    "booking.auto_promoted": "Waitlisted booking approved",
    "booking.cancelled": "Booking cancelled",
    "booking.checkin": "Equipment checked in",
    "booking.rejected": "Booking rejected",
    "booking.returned": "Equipment returned",
    "booking.submitted": "Access requested",
    "booking.waitlisted": "Added to waitlist",
    "incident.damage": "Damage reported",
    "incident.delay": "Delay reported",
    "incident.failure": "Equipment failure reported",
    "institution.dns_verify": "Institution domain checked",
    "resource.created": "Resource listed",
}


def action_label(action: str) -> str:
    """Return a concise user-facing label for an immutable audit event key."""
    if action in AUDIT_ACTION_LABELS:
        return AUDIT_ACTION_LABELS[action]
    return action.replace(".", " ").replace("_", " ").strip().title()
