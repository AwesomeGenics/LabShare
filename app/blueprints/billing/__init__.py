from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AuditLog, Booking, BookingStatus

billing_bp = Blueprint("billing", __name__, template_folder="../../templates/billing")


@billing_bp.route("/")
@login_required
def index():
    # Gather ledger data for the current user's institution
    institution = current_user.institution

    # All bookings for the institution's resources
    from app.models import Resource
    if current_user.role.value == "admin":
        all_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(50).all()
    elif current_user.role.value == "owner":
        own_res = Resource.query.filter_by(owner_id=current_user.id).all()
        rid_list = [r.id for r in own_res]
        all_bookings = (
            Booking.query.filter(Booking.resource_id.in_(rid_list))
            .order_by(Booking.created_at.desc()).limit(50).all()
        )
    else:
        all_bookings = (
            Booking.query.filter_by(user_id=current_user.id)
            .order_by(Booking.created_at.desc()).limit(50).all()
        )

    # Summary stats
    total_committed = sum(
        b.computed_fee for b in all_bookings
        if b.status.value in ("approved", "active", "returned")
    )
    total_returned = sum(
        b.computed_fee for b in all_bookings if b.status == BookingStatus.returned
    )

    from app.services.billing_service import TIER_TAKE_RATES, InstitutionTier
    take_rate = TIER_TAKE_RATES.get(
        institution.tier if institution else InstitutionTier.free, 0.10
    ) if institution else 0.10

    return render_template(
        "billing/index.html",
        institution=institution,
        all_bookings=all_bookings,
        total_committed=total_committed,
        total_returned=total_returned,
        take_rate=take_rate,
    )
