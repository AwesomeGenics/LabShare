from flask import Blueprint, flash, redirect, render_template, request, url_for, abort
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Booking, BookingStatus
from app.services.custody_service import checkin, file_incident, return_item

custody_bp = Blueprint("custody", __name__, template_folder="../../templates/custody")


def _get_booking_or_403(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    # Only the booking owner (or admin) can manage custody
    if booking.user_id != current_user.id and current_user.role.value != "admin":
        abort(403)
    return booking


# ─────────────────────────────────────────────────────────────────────────────
# QR Scanner landing
# ─────────────────────────────────────────────────────────────────────────────

@custody_bp.route("/scan")
@login_required
def scan_page():
    # Find approved or active bookings for user
    approved = Booking.query.filter_by(user_id=current_user.id, status=BookingStatus.approved).first()
    active = Booking.query.filter_by(user_id=current_user.id, status=BookingStatus.active).first()
    all_user_bookings = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status.in_([BookingStatus.approved, BookingStatus.active])
    ).all()
    return render_template("custody/scan.html", approved=approved, active=active, all_user_bookings=all_user_bookings)


# ─────────────────────────────────────────────────────────────────────────────
# Check-in
# ─────────────────────────────────────────────────────────────────────────────

@custody_bp.route("/checkin/<int:booking_id>", methods=["GET", "POST"])
@login_required
def checkin_view(booking_id):
    booking = _get_booking_or_403(booking_id)
    error = None

    if request.method == "POST":
        resource_code = request.form.get("resource_code", "").strip()
        before_photo = request.files.get("before_photo")

        if not resource_code:
            error = "Resource code is required."
        elif not before_photo or not before_photo.filename:
            error = "A 'before' photo is required to check in."
        else:
            ok, err = checkin(
                booking=booking,
                actor_id=current_user.id,
                before_photo=before_photo,
                resource_code=resource_code,
                ip_address=request.remote_addr,
            )
            if ok:
                flash("Check-in successful! Your session is now active.", "success")
                return redirect(url_for("bookings.my_bookings"))
            else:
                error = err

    return render_template("custody/checkin.html", booking=booking, error=error)


# ─────────────────────────────────────────────────────────────────────────────
# Return
# ─────────────────────────────────────────────────────────────────────────────

@custody_bp.route("/return/<int:booking_id>", methods=["GET", "POST"])
@login_required
def return_view(booking_id):
    booking = _get_booking_or_403(booking_id)
    error = None

    if request.method == "POST":
        after_photo = request.files.get("after_photo")
        if not after_photo or not after_photo.filename:
            error = "An 'after' photo is required to complete the return."
        else:
            ok, err = return_item(
                booking=booking,
                actor_id=current_user.id,
                after_photo=after_photo,
                ip_address=request.remote_addr,
            )
            if ok:
                flash("Return complete! Thank you for using the facility.", "success")
                return redirect(url_for("bookings.my_bookings"))
            else:
                error = err

    return render_template("custody/return.html", booking=booking, error=error)


# ─────────────────────────────────────────────────────────────────────────────
# Incident report
# ─────────────────────────────────────────────────────────────────────────────

@custody_bp.route("/incident/<int:booking_id>", methods=["GET", "POST"])
@login_required
def incident_view(booking_id):
    booking = _get_booking_or_403(booking_id)
    error = None

    if request.method == "POST":
        incident_type = request.form.get("incident_type", "")
        damage_notes = request.form.get("damage_notes", "").strip()
        incident_photo = request.files.get("incident_photo")

        ok, err = file_incident(
            booking=booking,
            actor_id=current_user.id,
            incident_type=incident_type,
            damage_notes=damage_notes,
            incident_photo=incident_photo if incident_photo and incident_photo.filename else None,
            ip_address=request.remote_addr,
        )
        if ok:
            flash("Incident report filed.", "success")
            return redirect(url_for("bookings.my_bookings"))
        else:
            error = err

    return render_template("custody/incident.html", booking=booking, error=error)
