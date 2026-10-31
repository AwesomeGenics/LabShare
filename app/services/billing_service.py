"""
app/services/billing_service.py

Billing, take-rate engine, damage surcharge, and AI compliance scan.
All payment processing and AI calls are MOCKED behind this service interface.
"""

import random
from app.models import Booking, Institution, InstitutionTier, Resource


# ─────────────────────────────────────────────────────────────────────────────
# Take-rate engine
# ─────────────────────────────────────────────────────────────────────────────

TIER_TAKE_RATES = {
    InstitutionTier.free: 0.15,         # 15% for free tier
    InstitutionTier.enterprise: 0.05,   # 5% for enterprise
}


def compute_take_rate(booking: Booking, institution: Institution) -> dict:
    """
    # MOCK — Compute platform take-rate on a cross-org rental.
    In production this would integrate with Stripe / institutional billing.

    Returns a dict with base_fee, take_rate_pct, platform_cut, net_to_owner.
    """
    rate = TIER_TAKE_RATES.get(institution.tier, 0.10)
    base = booking.computed_fee
    cut = round(base * rate, 2)
    return {
        "base_fee": base,
        "take_rate_pct": int(rate * 100),
        "platform_cut": cut,
        "net_to_owner": round(base - cut, 2),
    }


def compute_damage_surcharge(resource: Resource, damage_protection: bool) -> float:
    """
    Compute optional damage protection surcharge.
    Fee = deposit × category_risk_multiplier.
    """
    RISK = {
        "Analytical Instruments": 0.12,
        "Cleanrooms": 0.08,
        "Labs": 0.06,
        "3D Printers": 0.04,
        "CNC": 0.08,
        "Cameras": 0.05,
        "High-Performance Compute": 0.06,
        "BioSafety Spaces": 0.07,
    }
    if not damage_protection:
        return 0.0
    risk = RISK.get(resource.category.value, 0.07)
    return round(resource.deposit * risk, 2)


# ─────────────────────────────────────────────────────────────────────────────
# AI Compliance Scan  (Enterprise only)
# ─────────────────────────────────────────────────────────────────────────────

def mock_ai_compliance_scan(document_url: str | None) -> dict:
    """
    # MOCK — Simulate an AI-powered document scan for safety certificates
    and insurance forms (enterprise-only feature).

    In production this would call a vision-LLM API to extract and verify
    document fields against institutional compliance requirements.

    Returns:
        dict with keys: passed (bool), score (0-100), reasons (list[str]),
        summary (str), flagged_fields (list[str])
    """
    if not document_url:
        return {
            "passed": False,
            "score": 0,
            "reasons": ["No document uploaded."],
            "summary": "Document scan skipped — no file provided.",
            "flagged_fields": [],
        }

    # Simulate pass/fail (demo: 75% pass rate)
    passed = random.random() < 0.75
    score = random.randint(78, 98) if passed else random.randint(20, 59)

    if passed:
        return {
            "passed": True,
            "score": score,
            "reasons": ["Safety certificate valid.", "Insurance coverage confirmed."],
            "summary": f"Document verified. Compliance score: {score}/100.",
            "flagged_fields": [],
        }
    else:
        flags = random.sample(
            ["expiry_date", "institution_name", "coverage_amount", "signature"],
            k=random.randint(1, 2),
        )
        return {
            "passed": False,
            "score": score,
            "reasons": [
                f"Field '{f}' could not be verified." for f in flags
            ],
            "summary": f"Compliance check failed. Score: {score}/100. Manual review required.",
            "flagged_fields": flags,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tier enforcement (resource creation)
# ─────────────────────────────────────────────────────────────────────────────

def enforce_resource_limit(owner, institution: Institution, limit: int = 5) -> tuple[bool, str | None]:
    """
    Block resource creation if the owner's institution is on the free tier
    and already at the resource cap.
    """
    if institution.tier == InstitutionTier.enterprise:
        return True, None
    from app.models import Resource
    count = Resource.query.filter_by(owner_id=owner.id).count()
    if count >= limit:
        return False, (
            f"Free tier allows max {limit} resources. "
            "Upgrade to Enterprise for unlimited listings."
        )
    return True, None
