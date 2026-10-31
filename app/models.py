"""
All 7 data models for the Campus & Community Resource Sharing Platform.

AuditLog is append-only: before_update and before_delete SQLAlchemy event
listeners raise RuntimeError to prevent any mutation after insert.
"""

import enum
import secrets
from datetime import datetime, timezone
from pathlib import Path

from flask_login import UserMixin
from sqlalchemy import event

from app.extensions import db


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UserRole(str, enum.Enum):
    student = "student"
    owner = "owner"
    admin = "admin"


class InstitutionTier(str, enum.Enum):
    free = "free"
    enterprise = "enterprise"


class DomainStatus(str, enum.Enum):
    unverified = "unverified"
    pending = "pending"
    verified = "verified"


class ResourceCategory(str, enum.Enum):
    labs = "Labs"
    cleanrooms = "Cleanrooms"
    printers_3d = "3D Printers"
    cnc = "CNC"
    cameras = "Cameras"
    analytical = "Analytical Instruments"
    compute = "High-Performance Compute"
    biosafety = "BioSafety Spaces"


class BookingStatus(str, enum.Enum):
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    waitlisted = "waitlisted"
    active = "active"
    returned = "returned"
    cancelled = "cancelled"


# ---------------------------------------------------------------------------
# 1. Institution
# ---------------------------------------------------------------------------


class Institution(db.Model):
    __tablename__ = "institutions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    domain = db.Column(db.String(100), nullable=False, unique=True)
    tier = db.Column(db.Enum(InstitutionTier), nullable=False, default=InstitutionTier.free)
    dns_token = db.Column(db.String(64), nullable=False, default=lambda: secrets.token_hex(16))
    verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    users = db.relationship("User", back_populates="institution", lazy="dynamic")
    resources = db.relationship("Resource", back_populates="institution", lazy="dynamic")

    def __repr__(self):
        return f"<Institution {self.name} ({self.tier.value})>"


# ---------------------------------------------------------------------------
# 2. User
# ---------------------------------------------------------------------------


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.student)
    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"), nullable=True)
    institutional_domain_status = db.Column(
        db.Enum(DomainStatus), nullable=False, default=DomainStatus.unverified
    )
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    institution = db.relationship("Institution", back_populates="users")
    bookings = db.relationship("Booking", back_populates="user", lazy="dynamic")
    owned_resources = db.relationship("Resource", back_populates="owner", lazy="dynamic")
    training_records = db.relationship("TrainingRecord", back_populates="user", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="actor", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.email} [{self.role.value}]>"


# ---------------------------------------------------------------------------
# 3. Resource
# ---------------------------------------------------------------------------


class Resource(db.Model):
    __tablename__ = "resources"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.Enum(ResourceCategory), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    conditions = db.Column(db.Text, nullable=True)  # usage rules / safety notes
    deposit = db.Column(db.Float, nullable=False, default=0.0)
    hourly_price = db.Column(db.Float, nullable=False, default=0.0)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    owner = db.relationship("User", back_populates="owned_resources")
    institution = db.relationship("Institution", back_populates="resources")
    bookings = db.relationship("Booking", back_populates="resource", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="resource", lazy="dynamic")

    @property
    def display_image(self) -> str:
        """Return a curated instrument photograph or an appropriate local fallback."""
        static_root = Path(__file__).parent / "static"
        if self.image_url and self.image_url.startswith("/static/"):
            relative_path = self.image_url.removeprefix("/static/")
            image_path = static_root / relative_path
            if relative_path.startswith(("uploads/", "img/instruments/photos/")):
                if image_path.is_file():
                    return self.image_url
        if self.image_url and self.image_url.startswith("https://"):
            # Only allow images hosted by the institutions whose public facility
            # catalogs were used to curate the inventory below.
            from urllib.parse import urlparse

            host = (urlparse(self.image_url).hostname or "").lower()
            if host in {"materials.iisc.ac.in", "iisc.ac.in"}:
                return self.image_url
        name_lower = self.name.lower()
        if "cryo" in name_lower or "krios" in name_lower:
            return "/static/img/instruments/photos/cryo_tem_photo.jpg"
        elif any(term in name_lower for term in ("jeol", "2100", "electron microscope", "tem", "sem")):
            return "/static/img/instruments/photos/jeol_tem_photo.jpg"
        elif any(term in name_lower for term in ("cleanroom", "clean room", "nanofab", "fabrication lab")):
            return "/static/img/instruments/photos/cleanroom_photo.jpg"
        elif "nmr" in name_lower or "ascend" in name_lower:
            return "/static/img/instruments/photos/nmr_photo.jpg"
        elif any(term in name_lower for term in ("pravega", "compute", "hpc", "cluster", "server")):
            return "/static/img/instruments/photos/hpc_photo.jpg"
        elif "novaseq" in name_lower or "sequencer" in name_lower or "illumina" in name_lower:
            return "/static/img/instruments/photos/sequencer_photo.jpg"
        elif any(term in name_lower for term in ("lab", "laboratory", "workshop", "clean room")):
            return "/static/img/instruments/photos/cleanroom_photo.jpg"
        elif "3d" in name_lower or "printer" in name_lower or "formlabs" in name_lower:
            return "/static/img/instruments/photos/printer_3d_photo.jpg"
        elif any(term in name_lower for term in ("cnc", "haas", "milling")):
            return "/static/img/instruments/photos/cnc_photo.jpg"
        
        # Category fallbacks
        cat_map = {
            ResourceCategory.cleanrooms: "/static/img/instruments/photos/cleanroom_photo.jpg",
            ResourceCategory.analytical: "/static/img/instruments/photos/cryo_tem_photo.jpg",
            ResourceCategory.compute: "/static/img/instruments/photos/hpc_photo.jpg",
            ResourceCategory.biosafety: "/static/img/instruments/photos/sequencer_photo.jpg",
            ResourceCategory.printers_3d: "/static/img/instruments/photos/printer_3d_photo.jpg",
            ResourceCategory.cnc: "/static/img/instruments/photos/cnc_photo.jpg",
            ResourceCategory.cameras: "/static/img/instruments/photos/jeol_tem_photo.jpg",
            ResourceCategory.labs: "/static/img/instruments/photos/cleanroom_photo.jpg",
        }
        return cat_map.get(self.category, "/static/img/instruments/photos/cleanroom_photo.jpg")

    def __repr__(self):
        return f"<Resource {self.name}>"


# ---------------------------------------------------------------------------
# 4. Booking
# ---------------------------------------------------------------------------


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.Enum(BookingStatus), nullable=False, default=BookingStatus.submitted)
    project_scope = db.Column(db.Text, nullable=True)
    start_at = db.Column(db.DateTime, nullable=True)
    end_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    damage_protection = db.Column(db.Boolean, nullable=False, default=False)
    surcharge = db.Column(db.Float, nullable=False, default=0.0)
    computed_fee = db.Column(db.Float, nullable=False, default=0.0)
    waitlist_position = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    resource = db.relationship("Resource", back_populates="bookings")
    user = db.relationship("User", back_populates="bookings")
    condition_logs = db.relationship("ConditionLog", back_populates="booking", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="booking", lazy="dynamic")

    def __repr__(self):
        return f"<Booking #{self.id} [{self.status.value}]>"


# ---------------------------------------------------------------------------
# 5. ConditionLog
# ---------------------------------------------------------------------------


class ConditionLog(db.Model):
    __tablename__ = "condition_logs"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    check_in_photo_url = db.Column(db.String(500), nullable=True)
    return_photo_url = db.Column(db.String(500), nullable=True)
    damage_notes = db.Column(db.Text, nullable=True)
    incident_type = db.Column(db.String(50), nullable=True)  # delay / damage / failure
    incident_photo_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    booking = db.relationship("Booking", back_populates="condition_logs")

    def __repr__(self):
        return f"<ConditionLog booking={self.booking_id}>"


# ---------------------------------------------------------------------------
# 6. AuditLog  (APPEND-ONLY — no updates or deletes allowed)
# ---------------------------------------------------------------------------


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action_type = db.Column(db.String(100), nullable=False)
    previous_state = db.Column(db.String(100), nullable=True)
    new_state = db.Column(db.String(100), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    resource = db.relationship("Resource", back_populates="audit_logs")
    booking = db.relationship("Booking", back_populates="audit_logs")
    actor = db.relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action_type} by actor={self.actor_id}>"


# Block ALL updates and deletes on AuditLog rows
@event.listens_for(AuditLog, "before_update")
def _block_audit_update(mapper, connection, target):
    raise RuntimeError("AuditLog rows are immutable — updates are not permitted.")


@event.listens_for(AuditLog, "before_delete")
def _block_audit_delete(mapper, connection, target):
    raise RuntimeError("AuditLog rows are immutable — deletes are not permitted.")


# ---------------------------------------------------------------------------
# 7. TrainingRecord
# ---------------------------------------------------------------------------


class TrainingRecord(db.Model):
    __tablename__ = "training_records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    resource_category = db.Column(db.Enum(ResourceCategory), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="training_records")

    def __repr__(self):
        return f"<TrainingRecord user={self.user_id} cat={self.resource_category.value}>"
