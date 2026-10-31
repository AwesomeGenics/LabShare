"""
app/services/catalog_service.py

Business logic for resource search, filter, availability, and tier enforcement.
"""

from app.config import DevelopmentConfig
from app.extensions import db
from app.models import Booking, BookingStatus, Institution, InstitutionTier, Resource, ResourceCategory


def search_resources(
    query: str | None = None,
    category: str | None = None,
    location: str | None = None,
    available_only: bool = False,
    institution_id: int | None = None,
) -> list[Resource]:
    """Search and filter resources. Returns a list ordered by creation date desc."""
    q = Resource.query

    if query:
        like = f"%{query}%"
        q = q.filter(
            db.or_(
                Resource.name.ilike(like),
                Resource.location.ilike(like),
                Resource.conditions.ilike(like),
                Resource.institution.has(Institution.name.ilike(like)),
            )
        )

    if category:
        # Match category by value string
        matched = None
        for cat in ResourceCategory:
            if cat.value.lower() == category.lower() or cat.name.lower() == category.lower():
                matched = cat
                break
        if matched:
            q = q.filter(Resource.category == matched)

    if location:
        q = q.filter(Resource.location.ilike(f"%{location}%"))

    if institution_id:
        q = q.filter(Resource.institution_id == institution_id)

    if available_only:
        q = q.filter(Resource.is_available.is_(True))

    rows = q.order_by(Resource.name, Resource.id).all()
    if institution_id or len(rows) < 2:
        return rows

    # Round-robin colleges so a catalog expanded in one migration does not
    # visually bury other institutions beneath a block of new listings.
    grouped: dict[int, list[Resource]] = {}
    for resource in rows:
        grouped.setdefault(resource.institution_id, []).append(resource)
    interleaved: list[Resource] = []
    while any(grouped.values()):
        for institution_resources in grouped.values():
            if institution_resources:
                interleaved.append(institution_resources.pop(0))
    return interleaved


def get_resource_or_404(resource_id: int) -> Resource:
    return db.get_or_404(Resource, resource_id)


def check_tier_limit(owner_id: int, institution: Institution) -> tuple[bool, str | None]:
    """
    Enforce free-tier resource cap (max 5 resources).
    Returns (allowed: bool, error_message: str | None).
    """
    if institution.tier == InstitutionTier.enterprise:
        return True, None

    count = Resource.query.filter_by(owner_id=owner_id).count()
    limit = DevelopmentConfig.FREE_TIER_RESOURCE_LIMIT
    if count >= limit:
        return False, (
            f"Free tier allows a maximum of {limit} resources. "
            "Upgrade to Enterprise for unlimited listings."
        )
    return True, None


def get_active_booking_for_resource(resource_id: int) -> Booking | None:
    """Return the currently active booking for a resource, if any."""
    return Booking.query.filter_by(
        resource_id=resource_id, status=BookingStatus.active
    ).first()


def get_waitlist_count(resource_id: int) -> int:
    """Return number of waitlisted bookings for a resource."""
    return Booking.query.filter_by(
        resource_id=resource_id, status=BookingStatus.waitlisted
    ).count()
