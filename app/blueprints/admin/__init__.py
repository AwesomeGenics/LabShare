from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from app.extensions import db
from app.models import AuditLog, Booking, Institution, InstitutionTier, Resource, User
from app.services.auth_service import require_role
from app.services.audit_service import AUDIT_ACTION_LABELS, record_event

admin_bp = Blueprint("admin", __name__, template_folder="../../templates/admin")


@admin_bp.route("/console")
@login_required
@require_role("admin")
def console():
    institutions = Institution.query.order_by(Institution.name).all()
    users = User.query.order_by(User.name).all()
    resources = Resource.query.order_by(Resource.name).all()
    recent_audit = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(20).all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()

    stats = {
        "institutions": len(institutions),
        "users": len(users),
        "resources": len(resources),
        "bookings": Booking.query.count(),
        "enterprise": sum(1 for i in institutions if i.tier == InstitutionTier.enterprise),
        "verified": sum(1 for i in institutions if i.verified),
    }

    return render_template(
        "admin/console.html",
        institutions=institutions,
        users=users,
        resources=resources,
        recent_audit=recent_audit,
        action_labels=AUDIT_ACTION_LABELS,
        bookings=bookings,
        stats=stats,
    )


@admin_bp.route("/institution/<int:inst_id>/toggle-tier", methods=["POST"])
@login_required
@require_role("admin")
def toggle_tier(inst_id):
    institution = Institution.query.get_or_404(inst_id)
    old_tier = institution.tier.value
    if institution.tier == InstitutionTier.free:
        institution.tier = InstitutionTier.enterprise
    else:
        institution.tier = InstitutionTier.free
    db.session.flush()
    record_event(
        actor_id=current_user.id,
        action_type="admin.tier_change",
        previous_state=old_tier,
        new_state=institution.tier.value,
        ip_address=request.remote_addr,
        notes=f"Institution: {institution.name}",
    )
    db.session.commit()
    flash(f"{institution.name} tier changed to {institution.tier.value}.", "success")
    return redirect(url_for("admin.console"))


@admin_bp.route("/institution/<int:inst_id>/verify", methods=["POST"])
@login_required
@require_role("admin")
def verify_institution(inst_id):
    institution = Institution.query.get_or_404(inst_id)
    institution.verified = True
    for user in institution.users:
        from app.models import DomainStatus
        user.institutional_domain_status = DomainStatus.verified
    db.session.flush()
    record_event(
        actor_id=current_user.id,
        action_type="admin.institution_verified",
        new_state="verified",
        ip_address=request.remote_addr,
        notes=f"Institution: {institution.name}",
    )
    db.session.commit()
    flash(f"{institution.name} manually verified.", "success")
    return redirect(url_for("admin.console"))
