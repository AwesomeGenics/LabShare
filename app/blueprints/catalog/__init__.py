from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Institution, Resource, ResourceCategory, TrainingRecord
from app.services.auth_service import require_role
from app.services.audit_service import record_event
from app.services.catalog_service import (
    check_tier_limit,
    get_active_booking_for_resource,
    get_resource_or_404,
    get_waitlist_count,
    search_resources,
)

catalog_bp = Blueprint("catalog", __name__, template_folder="../../templates/catalog")


# ─────────────────────────────────────────────────────────────────────────────
# Public landing page  (Screen 1)
# ─────────────────────────────────────────────────────────────────────────────

@catalog_bp.route("/")
def landing():
    institutions = Institution.query.order_by(Institution.name).all()
    resources = []
    for institution in institutions:
        featured = Resource.query.filter_by(
            institution_id=institution.id, is_available=True
        ).order_by(Resource.name).first()
        if featured:
            resources.append(featured)
    if len(resources) < 6:
        selected_ids = {resource.id for resource in resources}
        for institution in sorted(institutions, key=lambda row: row.resources.count(), reverse=True):
            for resource in institution.resources.filter_by(is_available=True).order_by(Resource.name):
                if resource.id not in selected_ids:
                    resources.append(resource)
                    selected_ids.add(resource.id)
                    break
            if len(resources) == 6:
                break
    resources = resources[:6]
    return render_template(
        "catalog/landing.html",
        resources=resources,
        institutions=institutions,
        categories=list(ResourceCategory),
        resource_count=Resource.query.count(),
        available_count=Resource.query.filter_by(is_available=True).count(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Catalog index with search/filter  (Screen 3)
# ─────────────────────────────────────────────────────────────────────────────

@catalog_bp.route("/catalog/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    college = request.args.get("college", "").strip()
    available_only = request.args.get("available") == "1"

    resources = search_resources(
        query=q or None,
        category=category or None,
        available_only=available_only,
        institution_id=int(college) if college.isdigit() else None,
    )
    categories = list(ResourceCategory)
    institutions = Institution.query.order_by(Institution.name).all()
    return render_template(
        "catalog/index.html",
        resources=resources,
        categories=categories,
        q=q,
        selected_category=category,
        institutions=institutions,
        selected_college=college,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Resource detail  (Screen 4)
# ─────────────────────────────────────────────────────────────────────────────

@catalog_bp.route("/catalog/<int:resource_id>")
def detail(resource_id):
    resource = get_resource_or_404(resource_id)

    # Check user training status
    has_training = False
    if current_user.is_authenticated:
        has_training = bool(
            TrainingRecord.query.filter_by(
                user_id=current_user.id, resource_category=resource.category
            ).first()
        )

    active_booking = get_active_booking_for_resource(resource_id)
    waitlist_count = get_waitlist_count(resource_id)

    return render_template(
        "catalog/detail.html",
        resource=resource,
        has_training=has_training,
        active_booking=active_booking,
        waitlist_count=waitlist_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# New resource form  (Owners only)
# ─────────────────────────────────────────────────────────────────────────────

@catalog_bp.route("/catalog/new", methods=["GET", "POST"])
@login_required
@require_role("owner", "admin")
def new_resource():
    categories = list(ResourceCategory)
    error = None

    if request.method == "POST":
        # Tier enforcement
        allowed, tier_err = check_tier_limit(current_user, current_user.institution)
        if not allowed:
            error = tier_err
        else:
            try:
                cat_value = request.form.get("category", "")
                cat_enum = next(
                    (c for c in ResourceCategory if c.value == cat_value), None
                )
                if not cat_enum:
                    raise ValueError(f"Invalid category: {cat_value}")

                resource = Resource(
                    owner_id=current_user.id,
                    institution_id=current_user.institution_id,
                    name=request.form["name"].strip(),
                    category=cat_enum,
                    location=request.form["location"].strip(),
                    conditions=request.form.get("conditions", "").strip() or None,
                    deposit=float(request.form.get("deposit", 0)),
                    hourly_price=float(request.form.get("hourly_price", 0)),
                    is_available=True,
                )
                db.session.add(resource)
                db.session.flush()

                record_event(
                    actor_id=current_user.id,
                    action_type="resource.created",
                    new_state="available",
                    resource_id=resource.id,
                    ip_address=request.remote_addr,
                )
                db.session.commit()
                flash(f"Resource '{resource.name}' created successfully.", "success")
                return redirect(url_for("catalog.detail", resource_id=resource.id))
            except (ValueError, KeyError) as e:
                error = str(e)

    return render_template(
        "catalog/new_resource.html",
        categories=categories,
        error=error,
    )
