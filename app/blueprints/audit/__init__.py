from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AuditLog, Booking, Resource, User
from app.services.auth_service import require_role
from app.services.audit_service import AUDIT_ACTION_LABELS, action_label

audit_bp = Blueprint("audit", __name__, template_folder="../../templates/audit")


@audit_bp.route("/")
@login_required
def ledger():
    # Scoping: admin sees all; owner sees own resources; student sees own bookings
    role = current_user.role.value

    # Filter params
    resource_id = request.args.get("resource_id", type=int)
    booking_id = request.args.get("booking_id", type=int)
    actor_id = request.args.get("actor_id", type=int)
    action_type = request.args.get("action_type", "").strip()

    q = AuditLog.query

    if role == "student":
        # Student sees only events on their own bookings
        own_booking_ids = [
            b.id for b in Booking.query.filter_by(user_id=current_user.id).all()
        ]
        q = q.filter(
            db.or_(
                AuditLog.booking_id.in_(own_booking_ids),
                AuditLog.actor_id == current_user.id,
            )
        )
    elif role == "owner":
        # Owner sees events on their resources
        own_resource_ids = [
            r.id for r in Resource.query.filter_by(owner_id=current_user.id).all()
        ]
        q = q.filter(
            db.or_(
                AuditLog.resource_id.in_(own_resource_ids),
                AuditLog.actor_id == current_user.id,
            )
        )
    # admin: no additional filter

    if resource_id:
        q = q.filter(AuditLog.resource_id == resource_id)
    if booking_id:
        q = q.filter(AuditLog.booking_id == booking_id)
    if actor_id:
        q = q.filter(AuditLog.actor_id == actor_id)
    if action_type:
        q = q.filter(AuditLog.action_type.ilike(f"%{action_type}%"))

    logs = q.order_by(AuditLog.created_at.desc()).limit(200).all()

    # For filter dropdowns
    all_resources = Resource.query.order_by(Resource.name).all()
    all_users = User.query.order_by(User.name).all()
    distinct_actions = [
        row[0]
        for row in db.session.query(AuditLog.action_type)
        .distinct()
        .order_by(AuditLog.action_type)
        .all()
    ]
    action_options = [(action, action_label(action)) for action in distinct_actions]

    return render_template(
        "audit/ledger.html",
        logs=logs,
        all_resources=all_resources,
        all_users=all_users,
        distinct_actions=distinct_actions,
        action_options=action_options,
        action_labels=AUDIT_ACTION_LABELS,
        filter_resource_id=resource_id,
        filter_booking_id=booking_id,
        filter_actor_id=actor_id,
        filter_action_type=action_type,
    )
