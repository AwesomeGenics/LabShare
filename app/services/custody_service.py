"""
app/services/custody_service.py

Check-in, return, and incident report workflows with photo validation.
"""

import os
from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.models import Booking, BookingStatus, ConditionLog
from app.services.audit_service import record_event
from app.services.booking_service import auto_promote_waitlist
from app.services.upload_service import validate_and_save


def checkin(
    booking: Booking,
    actor_id: int,
    before_photo,        # FileStorage from request.files
    resource_code: str,
    ip_address: str | None = None,
) -> tuple[bool, str | None]:
    """
    Perform check-in:
      1. Validate resource code matches booking
      2. Save 'before' photo
      3. Transition booking → active
      4. Write audit log
    """
    if booking.status != BookingStatus.approved:
        return False, "Only approved bookings can be checked in."

    # Save before photo
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    photo_url, err = validate_and_save(before_photo, upload_folder, prefix="before")
    if err:
        return False, f"Before photo error: {err}"

    prev = booking.status.value
    booking.status = BookingStatus.active
    db.session.flush()

    cl = ConditionLog(
        booking_id=booking.id,
        check_in_photo_url=photo_url,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(cl)
    db.session.flush()

    record_event(
        actor_id=actor_id,
        action_type="booking.checkin",
        previous_state=prev,
        new_state="active",
        resource_id=booking.resource_id,
        booking_id=booking.id,
        ip_address=ip_address,
        notes=f"Resource code: {resource_code}. Before photo uploaded.",
    )
    db.session.commit()
    return True, None


def return_item(
    booking: Booking,
    actor_id: int,
    after_photo,         # FileStorage from request.files
    ip_address: str | None = None,
) -> tuple[bool, str | None]:
    """
    Perform return:
      1. Save 'after' photo
      2. Transition booking → returned
      3. Auto-promote next waitlisted booking
      4. Write audit log
    """
    if booking.status != BookingStatus.active:
        return False, "Only active bookings can be returned."

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    photo_url, err = validate_and_save(after_photo, upload_folder, prefix="after")
    if err:
        return False, f"After photo error: {err}"

    prev = booking.status.value
    booking.status = BookingStatus.returned
    db.session.flush()

    # Update or create condition log
    cl = ConditionLog.query.filter_by(booking_id=booking.id).order_by(
        ConditionLog.created_at.desc()
    ).first()
    if cl:
        cl.return_photo_url = photo_url
    else:
        cl = ConditionLog(
            booking_id=booking.id,
            return_photo_url=photo_url,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(cl)
    db.session.flush()

    record_event(
        actor_id=actor_id,
        action_type="booking.returned",
        previous_state=prev,
        new_state="returned",
        resource_id=booking.resource_id,
        booking_id=booking.id,
        ip_address=ip_address,
        notes="After photo uploaded. Item returned.",
    )
    db.session.flush()

    # Auto-promote waitlist
    from app.models import User
    actor = db.session.get(User, actor_id)
    auto_promote_waitlist(booking.resource_id, actor, ip_address)
    db.session.commit()
    return True, None


def file_incident(
    booking: Booking,
    actor_id: int,
    incident_type: str,
    damage_notes: str,
    incident_photo=None,  # optional FileStorage
    ip_address: str | None = None,
) -> tuple[bool, str | None]:
    """
    File an incident report attached to a booking's condition log.
    Allowed types: delay, damage, failure.
    """
    VALID_TYPES = ("delay", "damage", "failure")
    if incident_type not in VALID_TYPES:
        return False, f"Incident type must be one of: {', '.join(VALID_TYPES)}."
    if not damage_notes or not damage_notes.strip():
        return False, "Incident notes are required."

    photo_url = None
    if incident_photo and incident_photo.filename:
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        photo_url, err = validate_and_save(incident_photo, upload_folder, prefix="incident")
        if err:
            return False, f"Incident photo error: {err}"

    cl = ConditionLog(
        booking_id=booking.id,
        incident_type=incident_type,
        damage_notes=damage_notes.strip(),
        incident_photo_url=photo_url,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(cl)
    db.session.flush()

    record_event(
        actor_id=actor_id,
        action_type=f"incident.{incident_type}",
        previous_state=booking.status.value,
        new_state=booking.status.value,
        resource_id=booking.resource_id,
        booking_id=booking.id,
        ip_address=ip_address,
        notes=damage_notes.strip(),
    )
    db.session.commit()
    return True, None
