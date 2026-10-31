"""
seed.py — Idempotent seed script for the Campus & Community Resource Sharing Platform.
Configured with Indian Institutions, Researchers, National Facilities, and Rupee (₹) pricing.

Institutions:
  - IISc Bangalore (Enterprise, Verified)
  - IIT Bombay (Enterprise, Verified)
  - IIT Delhi (Free, Pending)
  - TIFR Mumbai (Free, Verified)

Users:
  - 1 Admin: Aarav Sharma (admin@iisc.ac.in)
  - 2 Owners: Dr. Rajesh Raman (rajesh.raman@iisc.ac.in), Prof. Sunita Krishnan (sunita.k@iitb.ac.in)
  - 3 Students: Ananya Deshmukh (ananya.d@iisc.ac.in), Rohan Sen (rohan.sen@iitb.ac.in), Priya Nair (priya.nair@iitd.ac.in)
  - 8 National Shared Resources across categories in Rupees (₹)
  - Training records, bookings across all 6 states, Condition logs & immutable Audit logs.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    AuditLog,
    Booking,
    BookingStatus,
    ConditionLog,
    DomainStatus,
    Institution,
    InstitutionTier,
    Resource,
    ResourceCategory,
    TrainingRecord,
    User,
    UserRole,
)

app = create_app("development")


def now():
    return datetime.now(timezone.utc)


def days_ago(n):
    return now() - timedelta(days=n)


def hours_from_now(n):
    return now() + timedelta(hours=n)


def write_audit(actor, action_type, prev=None, new=None, resource=None, booking=None, notes=None):
    """Helper to insert an AuditLog row (append-only)."""
    log = AuditLog(
        actor_id=actor.id,
        action_type=action_type,
        previous_state=prev,
        new_state=new,
        resource_id=resource.id if resource else None,
        booking_id=booking.id if booking else None,
        ip_address="127.0.0.1",
        notes=notes,
        created_at=now(),
    )
    db.session.add(log)
    return log


with app.app_context():
    print("Dropping all existing tables…")
    db.drop_all()
    print("Creating fresh database schema…")
    db.create_all()

    # ──────────────────────────────────────────────────────────────────────
    # 1. Indian Institutions
    # ──────────────────────────────────────────────────────────────────────
    iisc = Institution(
        name="IISc Bangalore",
        domain="iisc.ac.in",
        tier=InstitutionTier.enterprise,
        dns_token="synapse-fed-token-iisc-cense-98f24a1b8c00abc",
        verified=True,
    )
    iitb = Institution(
        name="IIT Bombay",
        domain="iitb.ac.in",
        tier=InstitutionTier.enterprise,
        dns_token="synapse-fed-token-iitb-powai-77a44b1c2233dfe",
        verified=True,
    )
    iitd = Institution(
        name="IIT Delhi",
        domain="iitd.ac.in",
        tier=InstitutionTier.free,
        dns_token="synapse-fed-token-iitd-hauzkhas-55c33a998811eef",
        verified=False,
    )
    tifr = Institution(
        name="TIFR Mumbai",
        domain="tifr.res.in",
        tier=InstitutionTier.free,
        dns_token="synapse-fed-token-tifr-colaba-112233445566778",
        verified=True,
    )

    db.session.add_all([iisc, iitb, iitd, tifr])
    db.session.flush()

    # ──────────────────────────────────────────────────────────────────────
    # 2. Users (Indian Academia)
    # ──────────────────────────────────────────────────────────────────────
    admin = User(
        name="Aarav Sharma",
        email="admin@iisc.ac.in",
        password_hash=generate_password_hash("admin1234"),
        role=UserRole.admin,
        institution_id=iisc.id,
        institutional_domain_status=DomainStatus.verified,
    )

    owner1 = User(
        name="Dr. Rajesh Raman",
        email="rajesh.raman@iisc.ac.in",
        password_hash=generate_password_hash("owner1234"),
        role=UserRole.owner,
        institution_id=iisc.id,
        institutional_domain_status=DomainStatus.verified,
    )

    owner2 = User(
        name="Prof. Sunita Krishnan",
        email="sunita.k@iitb.ac.in",
        password_hash=generate_password_hash("owner1234"),
        role=UserRole.owner,
        institution_id=iitb.id,
        institutional_domain_status=DomainStatus.verified,
    )

    student1 = User(
        name="Ananya Deshmukh",
        email="ananya.d@iisc.ac.in",
        password_hash=generate_password_hash("student1234"),
        role=UserRole.student,
        institution_id=iisc.id,
        institutional_domain_status=DomainStatus.verified,
    )

    student2 = User(
        name="Rohan Sen",
        email="rohan.sen@iitb.ac.in",
        password_hash=generate_password_hash("student1234"),
        role=UserRole.student,
        institution_id=iitb.id,
        institutional_domain_status=DomainStatus.verified,
    )

    student3 = User(
        name="Priya Nair",
        email="priya.nair@iitd.ac.in",
        password_hash=generate_password_hash("student1234"),
        role=UserRole.student,
        institution_id=iitd.id,
        institutional_domain_status=DomainStatus.unverified,
    )

    db.session.add_all([admin, owner1, owner2, student1, student2, student3])
    db.session.flush()

    # ──────────────────────────────────────────────────────────────────────
    # 3. Training Records
    # ──────────────────────────────────────────────────────────────────────
    tr1 = TrainingRecord(
        user_id=student1.id,
        resource_category=ResourceCategory.analytical,
        completed_at=days_ago(40),
    )
    tr2 = TrainingRecord(
        user_id=student1.id,
        resource_category=ResourceCategory.cleanrooms,
        completed_at=days_ago(30),
    )
    tr3 = TrainingRecord(
        user_id=student2.id,
        resource_category=ResourceCategory.cleanrooms,
        completed_at=days_ago(20),
    )
    tr4 = TrainingRecord(
        user_id=student2.id,
        resource_category=ResourceCategory.compute,
        completed_at=days_ago(15),
    )
    db.session.add_all([tr1, tr2, tr3, tr4])

    # ──────────────────────────────────────────────────────────────────────
    # 4. Resources (Indian Facilities in Rupees ₹)
    # ──────────────────────────────────────────────────────────────────────
    resources_data = [
        dict(
            owner_id=owner1.id,
            institution_id=iisc.id,
            name="Titan Krios G4 300 kV Cryo-TEM",
            category=ResourceCategory.analytical,
            location="IISc CeNSE • Biological Sciences Wing, Bengaluru",
            conditions=(
                "High-voltage (300 kV) cryogenic equipment. Pre-cooling of liquid nitrogen dewar "
                "required 90 minutes prior to session. SERB / ANRF grant pre-authorization required."
            ),
            deposit=40000.0,
            hourly_price=3500.0,
            is_available=True,
            image_url="/static/img/instruments/cryo_tem.png",
        ),
        dict(
            owner_id=owner2.id,
            institution_id=iitb.id,
            name="JEOL JEM-2100F Field Emission TEM",
            category=ResourceCategory.analytical,
            location="IIT Bombay • SAIF Facility, Powai, Mumbai",
            conditions=(
                "200 kV Field Emission, 0.19 nm point resolution. Cryo-Holder compatible. "
                "Mandatory safety certification log and cleanroom gowning required."
            ),
            deposit=25000.0,
            hourly_price=2200.0,
            is_available=True,
            image_url="/static/img/instruments/jeol_tem.png",
        ),
        dict(
            owner_id=owner1.id,
            institution_id=iisc.id,
            name="Class 100 ISO 5 Nanofab Cleanroom",
            category=ResourceCategory.cleanrooms,
            location="IISc CeNSE • National Nanofabrication Facility, Bengaluru",
            conditions=(
                "Deep Silicon RIE Etcher, Heidelberg Maskless Litho 405nm, N2 Glovebox Line. "
                "Level 3 Chemical & Toxic Gas Safety clearance mandatory."
            ),
            deposit=20000.0,
            hourly_price=1800.0,
            is_available=True,
            image_url="/static/img/instruments/cleanroom.png",
        ),
        dict(
            owner_id=owner2.id,
            institution_id=iitb.id,
            name="Bruker 800 MHz Ascend Ultra-Shield NMR",
            category=ResourceCategory.analytical,
            location="TIFR Mumbai • Chemical Sciences Block, Colaba",
            conditions=(
                "CryoProbe Prodigy, SampleJet 96-Pos autosampler. "
                "National user consortium slots available. Liquid helium refill status checked daily."
            ),
            deposit=30000.0,
            hourly_price=2800.0,
            is_available=False,
            image_url="/static/img/instruments/nmr.png",
        ),
        dict(
            owner_id=owner1.id,
            institution_id=iisc.id,
            name="Param Pravega High-Performance Computing Cluster",
            category=ResourceCategory.compute,
            location="IISc SERC Supercomputing Centre, Bengaluru",
            conditions=(
                "3.3 PFLOPS National Supercomputing Mission node. NVIDIA A100 Tensor Core GPUs. "
                "Slurm job scheduling queue with automated allocation."
            ),
            deposit=15000.0,
            hourly_price=1500.0,
            is_available=True,
            image_url="/static/img/instruments/hpc.png",
        ),
        dict(
            owner_id=owner2.id,
            institution_id=iitb.id,
            name="Illumina NovaSeq X Plus High-Throughput Sequencer",
            category=ResourceCategory.biosafety,
            location="IIT Bombay • Wadhwani Research Centre, Mumbai",
            conditions=(
                "25B Dual Flow Cells, automated library preparation, BSL-2 certified room. "
                "Direct FASTQ export to institutional cloud repository."
            ),
            deposit=35000.0,
            hourly_price=4500.0,
            is_available=True,
            image_url="/static/img/instruments/sequencer.png",
        ),
        dict(
            owner_id=owner1.id,
            institution_id=iisc.id,
            name="Formlabs Form 4 Industrial SLA 3D Printer",
            category=ResourceCategory.printers_3d,
            location="IISc Makerspace • Dept of Mechanical Engg, Bengaluru",
            conditions=(
                "Industrial photopolymer resin printer with wash & cure stations. "
                "Protective eyewear and nitrile gloves mandatory during post-processing."
            ),
            deposit=5000.0,
            hourly_price=600.0,
            is_available=True,
            image_url="/static/img/instruments/printer_3d.png",
        ),
        dict(
            owner_id=owner2.id,
            institution_id=iitb.id,
            name="Haas VF-2 5-Axis Precision CNC Machining Centre",
            category=ResourceCategory.cnc,
            location="IIT Bombay • Central Workshop & Fab Lab, Powai",
            conditions=(
                "40-taper spindle, 12,000 RPM, Renishaw probe toolsetter. "
                "Level 2 CAM & G-Code verification mandatory before spindle start."
            ),
            deposit=15000.0,
            hourly_price=1200.0,
            is_available=True,
            image_url="/static/img/instruments/cnc.png",
        ),
    ]

    resource_objs = []
    for rd in resources_data:
        r = Resource(**rd)
        db.session.add(r)
        resource_objs.append(r)
    db.session.flush()

    cryo_tem, jeol_tem, cleanroom, nmr, hpc, novaseq, printer_3d, cnc = resource_objs

    # ──────────────────────────────────────────────────────────────────────
    # 5. Bookings in various lifecycle states (Rupees ₹)
    # ──────────────────────────────────────────────────────────────────────

    # State 1: SUBMITTED
    b_submitted = Booking(
        resource_id=cryo_tem.id,
        user_id=student1.id,
        status=BookingStatus.submitted,
        project_scope="Cryo-EM structural analysis of Dengue virus NS1 glycoprotein dimer complex",
        start_at=hours_from_now(24),
        end_at=hours_from_now(26),
        computed_fee=7000.0,
        damage_protection=False,
        surcharge=0.0,
    )
    db.session.add(b_submitted)
    db.session.flush()
    write_audit(student1, "booking.submitted", prev=None, new="submitted",
                resource=cryo_tem, booking=b_submitted,
                notes="Submitted request for 2 hr Cryo-TEM slot. Scope: Dengue NS1.")

    # State 2: APPROVED
    b_approved = Booking(
        resource_id=cleanroom.id,
        user_id=student2.id,
        status=BookingStatus.approved,
        project_scope="E-Beam Lithography patterning of GaN HEMT semiconductor devices for 5G amplifiers",
        start_at=hours_from_now(48),
        end_at=hours_from_now(52),
        computed_fee=8640.0,
        damage_protection=True,
        surcharge=1440.0,
    )
    db.session.add(b_approved)
    db.session.flush()
    write_audit(student2, "booking.submitted", prev=None, new="submitted",
                resource=cleanroom, booking=b_approved)
    write_audit(owner1, "booking.approved", prev="submitted", new="approved",
                resource=cleanroom, booking=b_approved,
                notes="Approved with Damage Protection coverage under SERB Project grant.")

    # State 3: ACTIVE (Live Session)
    b_active = Booking(
        resource_id=jeol_tem.id,
        user_id=student1.id,
        status=BookingStatus.active,
        project_scope="High-resolution TEM of gold-silver core-shell nanorods for photothermal therapy",
        start_at=days_ago(0),
        end_at=hours_from_now(2),
        computed_fee=4400.0,
        damage_protection=False,
        surcharge=0.0,
    )
    db.session.add(b_active)
    db.session.flush()
    write_audit(student1, "booking.submitted", prev=None, new="submitted",
                resource=jeol_tem, booking=b_active)
    write_audit(owner2, "booking.approved", prev="submitted", new="approved",
                resource=jeol_tem, booking=b_active)
    write_audit(student1, "booking.checkin", prev="approved", new="active",
                resource=jeol_tem, booking=b_active,
                notes="QR Code TEM-2100 scanned. Before photo verified. Chamber vacuum stable.")
    cl_active = ConditionLog(
        booking_id=b_active.id,
        check_in_photo_url="/static/uploads/placeholder_before.jpg",
        created_at=now(),
    )
    db.session.add(cl_active)

    # State 4: RETURNED
    b_returned = Booking(
        resource_id=cleanroom.id,
        user_id=student1.id,
        status=BookingStatus.returned,
        project_scope="Photolithography mask alignment for microfluidic organ-on-a-chip diagnostic device",
        start_at=days_ago(4),
        end_at=days_ago(4) + timedelta(hours=4),
        computed_fee=7200.0,
        damage_protection=False,
        surcharge=0.0,
        created_at=days_ago(6),
    )
    db.session.add(b_returned)
    db.session.flush()
    write_audit(student1, "booking.submitted", prev=None, new="submitted",
                resource=cleanroom, booking=b_returned)
    write_audit(owner1, "booking.approved", prev="submitted", new="approved",
                resource=cleanroom, booking=b_returned)
    write_audit(student1, "booking.checkin", prev="approved", new="active",
                resource=cleanroom, booking=b_returned)
    write_audit(student1, "booking.returned", prev="active", new="returned",
                resource=cleanroom, booking=b_returned,
                notes="After photo uploaded. Cleanroom bay inspected. No contamination found.")
    cl_returned = ConditionLog(
        booking_id=b_returned.id,
        check_in_photo_url="/static/uploads/placeholder_before.jpg",
        return_photo_url="/static/uploads/placeholder_after.jpg",
        damage_notes="Cleanroom bay left in clean state, mask aligner recalibrated.",
        created_at=days_ago(4),
    )
    db.session.add(cl_returned)

    # State 5: REJECTED
    b_rejected = Booking(
        resource_id=nmr.id,
        user_id=student3.id,
        status=BookingStatus.rejected,
        project_scope="1H and 13C NMR conformational analysis of synthetic macrocyclic peptides",
        start_at=hours_from_now(72),
        end_at=hours_from_now(76),
        computed_fee=11200.0,
        damage_protection=False,
        rejection_reason="Applicant must complete mandatory Tier-3 High-Field NMR Safety Certification before requesting independent 800 MHz magnet access.",
    )
    db.session.add(b_rejected)
    db.session.flush()
    write_audit(student3, "booking.submitted", prev=None, new="submitted",
                resource=nmr, booking=b_rejected)
    write_audit(owner2, "booking.rejected", prev="submitted", new="rejected",
                resource=nmr, booking=b_rejected,
                notes="Rejected: Missing Tier-3 High-Field NMR Safety Certification.")

    # State 6: WAITLISTED
    b_waitlisted = Booking(
        resource_id=hpc.id,
        user_id=student2.id,
        status=BookingStatus.waitlisted,
        project_scope="Molecular dynamics simulations of SARS-CoV-2 spike variants on 64 A100 GPU nodes",
        start_at=hours_from_now(96),
        end_at=hours_from_now(104),
        computed_fee=12000.0,
        damage_protection=False,
        waitlist_position=1,
    )
    db.session.add(b_waitlisted)
    db.session.flush()
    write_audit(student2, "booking.submitted", prev=None, new="submitted",
                resource=hpc, booking=b_waitlisted)
    write_audit(owner1, "booking.waitlisted", prev="submitted", new="waitlisted",
                resource=hpc, booking=b_waitlisted,
                notes="Queue full. Assigned FIFO waitlist position #1.")

    db.session.commit()

    # Expand the freshly-created demo database with the same source-checked,
    # idempotent catalog used by the running app. This preserves the sample
    # bookings/audit history while dropping unsupported unused demo listings.
    from scripts.populate_verified_catalog import main as populate_verified_catalog

    populate_verified_catalog(app)

    print("\n✅ Seed complete with Indian Institutions & Rupee units (₹)!")
    print(f"   Institutions : {Institution.query.count()} (IISc, IIT Bombay, IIT Delhi, TIFR)")
    print(f"   Users        : {User.query.count()} (Admin: 1, Owners: 2, Students: 3)")
    print(f"   Resources    : {Resource.query.count()} (National research equipment in ₹)")
    print(f"   Bookings     : {Booking.query.count()} (submitted, approved, active, returned, rejected, waitlisted)")
    print(f"   TrainingRecs : {TrainingRecord.query.count()}")
    print(f"   AuditLogs    : {AuditLog.query.count()} (Immutable ledger)")
    print("\nCredentials for testing:")
    print("  admin@iisc.ac.in        / admin1234   [admin]")
    print("  rajesh.raman@iisc.ac.in / owner1234   [owner - IISc CeNSE]")
    print("  sunita.k@iitb.ac.in     / owner1234   [owner - IIT Bombay]")
    print("  ananya.d@iisc.ac.in     / student1234 [student - IISc]")
    print("  rohan.sen@iitb.ac.in    / student1234 [student - IITB]")
    print("  priya.nair@iitd.ac.in   / student1234 [student - IITD]")
