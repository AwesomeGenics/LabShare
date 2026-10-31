from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, abort
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Booking, BookingStatus, Resource
from app.models import InstitutionTier
from app.services.auth_service import require_role
from app.services.booking_service import (
    approve_booking,
    cancel_booking,
    check_prerequisites,
    compute_fee,
    reject_booking,
    submit_request,
    waitlist_booking,
)
from app.services.billing_service import mock_ai_compliance_scan
from app.services.upload_service import validate_and_save

bookings_bp = Blueprint("bookings", __name__, template_folder="../../templates/bookings")


def _parse_dt(s):
    """Parse 'YYYY-MM-DDTHH:MM' datetime-local string."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _get_owned_booking_or_403(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if current_user.role.value != "admin" and booking.resource.owner_id != current_user.id:
        abort(403)
    return booking


# ─────────────────────────────────────────────────────────────────────────────
# Booking request  (Screen 5)
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route("/new/<int:resource_id>", methods=["GET", "POST"])
@login_required
def new_booking(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    prereq_ok, prereq_reason = check_prerequisites(current_user, resource)

    fee_preview = compute_fee(resource, None, None, False)
    error = None
    compliance_result = None

    if request.method == "POST":
        project_scope = request.form.get("project_scope", "").strip()
        start_str = request.form.get("start_at", "")
        end_str = request.form.get("end_at", "")
        damage_protection = request.form.get("damage_protection") == "1"
        institution = current_user.institution

        if institution and institution.tier == InstitutionTier.enterprise:
            certificate = request.files.get("safety_certificate")
            if not certificate or not certificate.filename:
                error = "Upload a safety certificate to continue."
            else:
                document_url, upload_error = validate_and_save(
                    certificate,
                    current_app.config["UPLOAD_FOLDER"],
                    prefix="safety_certificate",
                    allowed_extensions={"pdf", "jpg", "jpeg", "png", "webp"},
                )
                if upload_error:
                    error = upload_error
                else:
                    compliance_result = mock_ai_compliance_scan(document_url)
                    if not compliance_result["passed"]:
                        error = "Certificate check needs review. " + " ".join(compliance_result["reasons"])

        start_at = _parse_dt(start_str)
        end_at = _parse_dt(end_str)

        if not error and (not start_at or not end_at):
            error = "Choose a valid start and end time."
        elif not error and end_at <= start_at:
            error = "End time must be after start time."
        elif not error and not project_scope:
            error = "Research scope / objectives are required."
        elif not error:
            booking, err = submit_request(
                user=current_user,
                resource=resource,
                project_scope=project_scope,
                start_at=start_at,
                end_at=end_at,
                damage_protection=damage_protection,
                ip_address=request.remote_addr,
            )
            if err:
                error = err
            else:
                notice = "Booking request submitted. The owner will review it shortly."
                if compliance_result and compliance_result["passed"]:
                    notice = "Safety certificate passed. " + notice
                flash(notice, "success")
                return redirect(url_for("bookings.my_bookings"))

        # Re-compute fee for display
        if start_at and end_at:
            fee_preview = compute_fee(resource, start_at, end_at,
                                      request.form.get("damage_protection") == "1")

    return render_template(
        "bookings/request.html",
        resource=resource,
        prereq_ok=prereq_ok,
        prereq_reason=prereq_reason,
        fee_preview=fee_preview,
        error=error,
        compliance_result=compliance_result,
    )


# ─────────────────────────────────────────────────────────────────────────────
# My Bookings  (Screen 7)
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route("/my")
@login_required
def my_bookings():
    active = Booking.query.filter_by(
        user_id=current_user.id, status=BookingStatus.active
    ).all()
    upcoming = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status.in_([BookingStatus.approved, BookingStatus.submitted,
                            BookingStatus.waitlisted])
    ).order_by(Booking.start_at.asc()).all()
    past = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status.in_([BookingStatus.returned, BookingStatus.rejected,
                            BookingStatus.cancelled])
    ).order_by(Booking.created_at.desc()).limit(20).all()

    return render_template(
        "bookings/my_bookings.html",
        active=active,
        upcoming=upcoming,
        past=past,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Owner Dashboard  (Screen 6)
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route("/owner/dashboard")
@login_required
@require_role("owner", "admin")
def owner_dashboard():
    # Get all resources owned by this user
    owner_resource_ids = [
        r.id for r in Resource.query.filter_by(owner_id=current_user.id).all()
    ]

    pending_bookings = Booking.query.filter(
        Booking.resource_id.in_(owner_resource_ids),
        Booking.status == BookingStatus.submitted,
    ).order_by(Booking.created_at.asc()).all()

    approved_bookings = Booking.query.filter(
        Booking.resource_id.in_(owner_resource_ids),
        Booking.status == BookingStatus.approved,
    ).order_by(Booking.start_at.asc()).all()

    active_bookings = Booking.query.filter(
        Booking.resource_id.in_(owner_resource_ids),
        Booking.status == BookingStatus.active,
    ).all()

    my_resources = Resource.query.filter_by(owner_id=current_user.id).all()

    stats = {
        "pending": len(pending_bookings),
        "approved": len(approved_bookings),
        "active": len(active_bookings),
        "resources": len(my_resources),
    }

    return render_template(
        "bookings/owner_dashboard.html",
        pending_bookings=pending_bookings,
        approved_bookings=approved_bookings,
        active_bookings=active_bookings,
        my_resources=my_resources,
        stats=stats,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Approve / Reject / Waitlist actions
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route("/<int:booking_id>/approve", methods=["POST"])
@login_required
@require_role("owner", "admin")
def approve(booking_id):
    booking = _get_owned_booking_or_403(booking_id)
    if booking.status != BookingStatus.submitted:
        abort(409)
    approve_booking(booking, current_user, request.remote_addr)
    flash(f"Booking #{booking_id} approved.", "success")
    return redirect(url_for("bookings.owner_dashboard"))


@bookings_bp.route("/<int:booking_id>/reject", methods=["POST"])
@login_required
@require_role("owner", "admin")
def reject(booking_id):
    booking = _get_owned_booking_or_403(booking_id)
    if booking.status != BookingStatus.submitted:
        abort(409)
    reason = request.form.get("reason", "").strip()
    ok, err = reject_booking(booking, current_user, reason, request.remote_addr)
    if not ok:
        flash(err or "Rejection failed.", "error")
    else:
        flash(f"Booking #{booking_id} rejected.", "success")
    return redirect(url_for("bookings.owner_dashboard"))


@bookings_bp.route("/<int:booking_id>/waitlist", methods=["POST"])
@login_required
@require_role("owner", "admin")
def waitlist(booking_id):
    booking = _get_owned_booking_or_403(booking_id)
    if booking.status != BookingStatus.submitted:
        abort(409)
    waitlist_booking(booking, current_user, request.remote_addr)
    flash(f"Booking #{booking_id} added to waitlist.", "success")
    return redirect(url_for("bookings.owner_dashboard"))


@bookings_bp.route("/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    # Only the requester or admin/owner can cancel
    if booking.user_id != current_user.id:
        abort(403)
    cancel_booking(booking, current_user, request.remote_addr)
    flash(f"Booking #{booking_id} cancelled.", "success")
    return redirect(url_for("bookings.my_bookings"))
