"""
app/services/booking_service.py

Business logic for booking requests, prerequisite checks, approvals, rejections,
waitlisting, FIFO auto-promotion, and weekly quota enforcement.
"""

from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models import (
    Booking,
    BookingStatus,
    Resource,
    TrainingRecord,
    User,
)
from app.services.audit_service import record_event


# ─────────────────────────────────────────────────────────────────────────────
# Prerequisite check
# ─────────────────────────────────────────────────────────────────────────────

def check_prerequisites(user: User, resource: Resource) -> tuple[bool, str | None]:
    """
    Return (ok, reason). ok=True means the user may submit a booking request.
    Checks:
      1. User's domain is verified
      2. User has a TrainingRecord for the resource's category
    """
    if user.institutional_domain_status.value != "verified":
        return False, "Your institutional domain must be DNS-verified before booking."

    has_training = TrainingRecord.query.filter_by(
        user_id=user.id, resource_category=resource.category
    ).first()
    if not has_training:
        return False, (
            f"Training for '{resource.category.value}' is required. "
            "Please complete the mandatory safety training before requesting access."
        )

    return True, None


# ─────────────────────────────────────────────────────────────────────────────
# Quota check
# ─────────────────────────────────────────────────────────────────────────────

def check_weekly_quota(
    user: User, resource: Resource, requested_hours: float = 0
) -> tuple[bool, str | None]:
    """
    Enforce per-user weekly quota on high-demand resources (configured hours).
    Returns (ok, reason).
    """
    quota_hours = current_app.config.get("WEEKLY_QUOTA_HOURS", 8)
    week_start = datetime.now(timezone.utc) - timedelta(days=7)

    bookings = Booking.query.filter(
        Booking.user_id == user.id,
        Booking.resource_id == resource.id,
        Booking.status.in_([
            BookingStatus.submitted, BookingStatus.approved,
            BookingStatus.active, BookingStatus.returned,
        ]),
        Booking.created_at >= week_start,
    ).all()

    total_hours = sum(
        (b.end_at - b.start_at).total_seconds() / 3600
        for b in bookings
        if b.start_at and b.end_at
    )

    if total_hours + requested_hours > quota_hours:
        return False, (
            f"Weekly quota of {quota_hours}h reached for this resource. "
            "Your quota resets in 7 days."
        )
    return True, None


# ─────────────────────────────────────────────────────────────────────────────
# Fee computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_fee(resource: Resource, start_at: datetime, end_at: datetime,
                damage_protection: bool = False) -> dict:
    """Return a fee breakdown dict."""
    if start_at and end_at:
        hours = max((end_at - start_at).total_seconds() / 3600, 0)
    else:
        hours = 2.0  # default 2-hour block

    base = resource.hourly_price * hours

    # Damage protection surcharge: 8% of deposit per category risk
    RISK_MULTIPLIERS = {
        "Analytical Instruments": 0.12,
        "Cleanrooms": 0.08,
        "Labs": 0.06,
        "3D Printers": 0.04,
        "CNC": 0.08,
        "Cameras": 0.05,
        "High-Performance Compute": 0.06,
        "BioSafety Spaces": 0.07,
    }
    risk = RISK_MULTIPLIERS.get(resource.category.value, 0.07)
    surcharge = round(resource.deposit * risk, 2) if damage_protection else 0.0

    return {
        "hours": round(hours, 2),
        "base": round(base, 2),
        "surcharge": surcharge,
        "total": round(base + surcharge, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Submit booking request
# ─────────────────────────────────────────────────────────────────────────────

def submit_request(
    user: User,
    resource: Resource,
    project_scope: str,
    start_at: datetime | None,
    end_at: datetime | None,
    damage_protection: bool = False,
    ip_address: str | None = None,
) -> tuple[Booking | None, str | None]:
    """
    Validate and create a new booking in 'submitted' status.
    Returns (booking, error). On failure booking is None.
    """
    ok, reason = check_prerequisites(user, resource)
    if not ok:
        return None, reason

    requested_hours = (
        (end_at - start_at).total_seconds() / 3600
        if start_at and end_at else 2.0
    )
    if requested_hours <= 0:
        return None, "End time must be after start time."

    ok, reason = check_weekly_quota(user, resource, requested_hours)
    if not ok:
        return None, reason

    fee = compute_fee(resource, start_at, end_at, damage_protection)

    booking = Booking(
        resource_id=resource.id,
        user_id=user.id,
        status=BookingStatus.submitted,
        project_scope=project_scope,
        start_at=start_at,
        end_at=end_at,
        damage_protection=damage_protection,
        surcharge=fee["surcharge"],
        computed_fee=fee["total"],
    )
    db.session.add(booking)
    db.session.flush()

    record_event(
        actor_id=user.id,
        action_type="booking.submitted",
        new_state="submitted",
        resource_id=resource.id,
        booking_id=booking.id,
        ip_address=ip_address,
    )
    db.session.commit()
    return booking, None


# ─────────────────────────────────────────────────────────────────────────────
# Owner actions
# ─────────────────────────────────────────────────────────────────────────────

def approve_booking(booking: Booking, actor: User, ip_address: str | None = None) -> None:
    prev = booking.status.value
    booking.status = BookingStatus.approved
    db.session.flush()
    record_event(
        actor_id=actor.id,
        action_type="booking.approved",
        previous_state=prev,
        new_state="approved",
        resource_id=booking.resource_id,
        booking_id=booking.id,
        ip_address=ip_address,
    )
    db.session.commit()


def reject_booking(booking: Booking, actor: User, reason: str,
                   ip_address: str | None = None) -> tuple[bool, str | None]:
    if not reason or not reason.strip():
        return False, "A rejection reason is required."
    prev = booking.status.value
    booking.status = BookingStatus.rejected
    booking.rejection_reason = reason.strip()
    db.session.flush()
    record_event(
        actor_id=actor.id,
        action_type="booking.rejected",
        previous_state=prev,
        new_state="rejected",
        resource_id=booking.resource_id,
        booking_id=booking.id,
        ip_address=ip_address,
        notes=reason.strip(),
    )
    db.session.commit()
    return True, None


def waitlist_booking(booking: Booking, actor: User, ip_address: str | None = None) -> None:
    prev = booking.status.value
    # Compute FIFO position
    current_max = db.session.query(
        db.func.max(Booking.waitlist_position)
    ).filter_by(resource_id=booking.resource_id).scalar() or 0

    booking.status = BookingStatus.waitlisted
    booking.waitlist_position = current_max + 1
    db.session.flush()
    record_event(
        actor_id=actor.id,
        action_type="booking.waitlisted",
        previous_state=prev,
        new_state="waitlisted",
        resource_id=booking.resource_id,
        booking_id=booking.id,
        ip_address=ip_address,
        notes=f"Waitlist position #{booking.waitlist_position}",
    )
    db.session.commit()


def cancel_booking(booking: Booking, actor: User, ip_address: str | None = None) -> None:
    prev = booking.status.value
    booking.status = BookingStatus.cancelled
    db.session.flush()
    record_event(
        actor_id=actor.id,
        action_type="booking.cancelled",
        previous_state=prev,
        new_state="cancelled",
        resource_id=booking.resource_id,
        booking_id=booking.id,
        ip_address=ip_address,
    )
    db.session.flush()
    # Auto-promote the next waitlisted booking
    auto_promote_waitlist(booking.resource_id, actor, ip_address)
    db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# FIFO auto-promotion
# ─────────────────────────────────────────────────────────────────────────────

def auto_promote_waitlist(resource_id: int, actor: User, ip_address: str | None = None) -> None:
    """
    Promote the top-of-queue (lowest waitlist_position) waitlisted booking
    to 'approved' when a slot opens up.
    """
    next_booking = (
        Booking.query
        .filter_by(resource_id=resource_id, status=BookingStatus.waitlisted)
        .order_by(Booking.waitlist_position.asc())
        .first()
    )
    if not next_booking:
        return

    prev = next_booking.status.value
    next_booking.status = BookingStatus.approved
    next_booking.waitlist_position = None
    db.session.flush()
    record_event(
        actor_id=actor.id,
        action_type="booking.auto_promoted",
        previous_state=prev,
        new_state="approved",
        resource_id=resource_id,
        booking_id=next_booking.id,
        ip_address=ip_address,
        notes="Auto-promoted from waitlist.",
    )
