"""Add a source-checked Indian campus catalog without resetting user data.

Run with ``python3 scripts/populate_verified_catalog.py``. The script is
idempotent, keeps booking/audit history, and only removes unsupported demo
entries when they have no booking or audit references.

Institution sources used for the catalog:
* IISc Materials Engineering: https://materials.iisc.ac.in/facilities
* IISc MNCF: https://mncf.cense.iisc.ac.in/facilities-all/
* IISc IPC: https://ipc.iisc.ac.in/facilities.php
* IISc Physics: https://physics.iisc.ac.in/research/research-facilities/
* IIT Bombay instrument registry: https://instruments.iitb.ac.in/instrument-details
* IIT Bombay SAIF/CRNTS: https://www.crnts.iitb.ac.in/SaifFacilities.html
* IIT Delhi CRF: https://crf.iitd.ac.in/All-Facilities-/CRF_Facilities.html
* TIFR Mumbai: https://www.tifr.res.in/maincampus/campusresources.php
* TIFR NMR: https://www.tifr.res.in/~nmr/home_item1.html
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.extensions import db
from app.models import Institution, Resource, ResourceCategory, User, UserRole


LOCAL_PHOTOS = {
    "microscopy": "/static/img/instruments/photos/jeol_tem_photo.jpg",
    "electron microscopy": "/static/img/instruments/photos/cryo_tem_photo.jpg",
    "xray": "/static/img/instruments/photos/jeol_tem_photo.jpg",
    "nmr": "/static/img/instruments/photos/nmr_photo.jpg",
    "spectroscopy": "/static/img/instruments/photos/sequencer_photo.jpg",
    "thermal": "/static/img/instruments/photos/cnc_photo.jpg",
    "particle": "/static/img/instruments/photos/sequencer_photo.jpg",
    "cleanroom": "/static/img/instruments/photos/cleanroom_photo.jpg",
    "compute": "/static/img/instruments/photos/hpc_photo.jpg",
    "fabrication": "/static/img/instruments/photos/cnc_photo.jpg",
    "lab": "/static/img/instruments/photos/cleanroom_photo.jpg",
}

IISC_FACILITY_PHOTOS = {
    "electron microscopy": "https://materials.iisc.ac.in/assets/images/facilities/sem.png",
    "microscopy": "https://materials.iisc.ac.in/assets/images/facilities/afm.png",
    "xray": "https://materials.iisc.ac.in/assets/images/facilities/xpert.png",
    "thermal": "https://materials.iisc.ac.in/assets/images/facilities/dsc.png",
    "particle": "https://materials.iisc.ac.in/assets/images/facilities/zetasizer.png",
}


def catalog_photo(kind: str, sequence: int = 0) -> str:
    return LOCAL_PHOTOS.get(kind, LOCAL_PHOTOS["lab"])


def iisc_catalog_photo(kind: str, sequence: int = 0) -> str:
    if kind == "particle" and sequence % 2:
        return "https://materials.iisc.ac.in/assets/images/facilities/micromeritics.png"
    return IISC_FACILITY_PHOTOS.get(kind, catalog_photo(kind, sequence))


# These names are taken from the linked institution facility lists. The
# descriptions are intentionally short and do not imply open access or a rate.
CATALOG = {
    "iisc.ac.in": [
        ("JEOL JXA-8530F Electron Probe Microanalyser", "Analytical Instruments", "Materials Engineering · Electron Microscopy Lab", "electron microscopy"),
        ("JPK NanoWizard R3 Atomic Force Microscope", "Analytical Instruments", "Materials Engineering · Electron Microscopy Lab", "microscopy"),
        ("PANalytical X'Pert PRO X-ray Diffractometer", "Analytical Instruments", "Materials Engineering · X-ray Diffraction Lab", "xray"),
        ("Rigaku SmartLab X-ray Diffractometer", "Analytical Instruments", "Materials Engineering · X-ray Diffraction Lab", "xray"),
        ("Mettler-Toledo DSC 822e Differential Scanning Calorimeter", "Analytical Instruments", "Materials Engineering · Thermal Characterization Lab", "thermal"),
        ("NETZSCH STA 449 F3 Jupiter Thermal Analyser", "Analytical Instruments", "Materials Engineering · Thermal Characterization Lab", "thermal"),
        ("NETZSCH STA 409 TG-DTA Thermal Analyser", "Analytical Instruments", "Materials Engineering · Thermal Characterization Lab", "thermal"),
        ("Thermo Electron Atomic Absorption Spectrometer", "Analytical Instruments", "Materials Engineering · Particle and Pore Characterization Lab", "spectroscopy"),
        ("Malvern Zetasizer Nano ZEN 3690", "Analytical Instruments", "Materials Engineering · Particle and Pore Characterization Lab", "particle"),
        ("Micromeritics ASAP 2020 Micropore Analyser", "Analytical Instruments", "Materials Engineering · Particle and Pore Characterization Lab", "particle"),
        ("FEI Quanta 200 Environmental Scanning Electron Microscope", "Analytical Instruments", "Materials Engineering · Electron Microscopy Lab", "electron microscopy"),
        ("Instron 5967 Universal Testing System", "Analytical Instruments", "Materials Engineering · Mechanical Testing Lab", "thermal"),
        ("Zwick/Roell Z100 Universal Testing Machine", "Analytical Instruments", "Materials Engineering · Mechanical Testing Lab", "thermal"),
        ("Instron 8502 Fatigue Testing System", "Analytical Instruments", "Materials Engineering · Mechanical Testing Lab", "thermal"),
        ("Hysitron TI 950 Nanoindenter", "Analytical Instruments", "Materials Engineering · Indentation Lab", "microscopy"),
        ("Bruker Dimension ICON Atomic Force Microscope", "Analytical Instruments", "CeNSE · Micro and Nano Characterization Facility", "microscopy"),
        ("Oxford Instruments MFP-3D Origin+ Atomic Force Microscope", "Analytical Instruments", "CeNSE · Micro and Nano Characterization Facility", "microscopy"),
        ("Helios 5 UX DualBeam Focused Ion Beam SEM", "Analytical Instruments", "CeNSE · Micro and Nano Characterization Facility", "electron microscopy"),
        ("X-ray Photoelectron Spectrometer", "Analytical Instruments", "Department of Physics · Shared Facility", "xray"),
        ("Confocal Photoluminescence Raman Microscope", "Analytical Instruments", "Department of Physics · Shared Facility", "spectroscopy"),
        ("UV-Visible Spectrophotometer", "Analytical Instruments", "Inorganic and Physical Chemistry · Research Facilities", "spectroscopy"),
        ("Fourier-Transform Infrared Spectrometer", "Analytical Instruments", "Inorganic and Physical Chemistry · Research Facilities", "spectroscopy"),
        ("FT-Raman Spectrometer", "Analytical Instruments", "Inorganic and Physical Chemistry · Research Facilities", "spectroscopy"),
        ("Atomic Force Microscope", "Analytical Instruments", "Inorganic and Physical Chemistry · Research Facilities", "microscopy"),
        ("Single-Crystal X-ray Diffractometer", "Analytical Instruments", "Inorganic and Physical Chemistry · Research Facilities", "xray"),
        ("Powder X-ray Diffractometer", "Analytical Instruments", "Inorganic and Physical Chemistry · Research Facilities", "xray"),
        ("ESI Mass Spectrometry Facility", "Analytical Instruments", "Inorganic and Physical Chemistry · Mass Spectrometry Facility", "spectroscopy"),
        ("SQUID Magnetometer", "Analytical Instruments", "Inorganic and Physical Chemistry · Research Facilities", "thermal"),
        ("Semiconductor Processing Cleanroom", "Cleanrooms", "Department of Physics · Semiconductor Processing Facility", "cleanroom"),
        ("IISc Computational Research Cluster", "High-Performance Compute", "Materials Engineering · Computational Facilities", "compute"),
    ],
    "iitb.ac.in": [
        ("Field Emission Gun TEM with STEM, EDS and EELS (300 kV)", "Analytical Instruments", "SAIF · Ground Floor, Room 314", "electron microscopy"),
        ("Field Emission Gun TEM (200 kV)", "Analytical Instruments", "CSIF/SAIF · Ground Floor, Room 315-A", "electron microscopy"),
        ("Focused Ion Beam Scanning Electron Microscope", "Analytical Instruments", "SAIF/CSIF · Ground Floor, Room 306", "electron microscopy"),
        ("Field Emission Gun SEM", "Analytical Instruments", "Chemistry · New CESE-DESE Building", "electron microscopy"),
        ("Four-Dimensional X-ray Microscope", "Analytical Instruments", "CSIF · SAIF Room 103", "xray"),
        ("FTIR Imaging System", "Analytical Instruments", "SAIF/CSIF · First Floor, Lab 413-B", "spectroscopy"),
        ("Time-Resolved Fluorescence Spectroscopy and Microscopy System", "Analytical Instruments", "SAIF/CSIF · TRFSM Facility, Room 210-B", "spectroscopy"),
        ("600 MHz JEOL Nuclear Magnetic Resonance Spectrometer", "Analytical Instruments", "SAIF · IIT Bombay", "nmr"),
        ("CHNSO Elemental Analyser", "Analytical Instruments", "SAIF · IIT Bombay", "spectroscopy"),
        ("Inductively Coupled Plasma Mass Spectrometer", "Analytical Instruments", "SAIF · IIT Bombay", "spectroscopy"),
        ("Inductively Coupled Plasma Optical Emission Spectrometer", "Analytical Instruments", "SAIF · IIT Bombay", "spectroscopy"),
        ("GC-HRMS Mass Spectrometer", "Analytical Instruments", "SAIF · IIT Bombay", "spectroscopy"),
        ("High-Resolution LC-MS QTOF System", "Analytical Instruments", "SAIF · IIT Bombay", "spectroscopy"),
        ("Electron Spin Resonance Spectrometer", "Analytical Instruments", "SAIF · IIT Bombay", "spectroscopy"),
        ("Thermogravimetric and Differential Thermal Analyser", "Analytical Instruments", "SAIF · IIT Bombay", "thermal"),
        ("Differential Scanning Calorimeter", "Analytical Instruments", "SAIF · IIT Bombay", "thermal"),
        ("Time-of-Flight Secondary Ion Mass Spectrometer", "Analytical Instruments", "SAIF · IIT Bombay", "spectroscopy"),
        ("Stylus Profilometer", "Analytical Instruments", "SAIF · IIT Bombay", "microscopy"),
        ("Small-Angle X-ray Scattering Facility", "Analytical Instruments", "SAIF · IIT Bombay", "xray"),
    ],
    "iitd.ac.in": [
        ("400 MHz JEOL NMR Spectrometer with Liquid and Solid Probes", "Analytical Instruments", "CRF · Block V", "nmr"),
        ("400 MHz Bruker NMR Spectrometer", "Analytical Instruments", "CRF · Block V", "nmr"),
        ("500 MHz Bruker NMR Spectrometer", "Analytical Instruments", "CRF · Block V", "nmr"),
        ("SEM Carl Zeiss EVO 18", "Analytical Instruments", "CRF · Block 5", "electron microscopy"),
        ("FE-SEM with EDS (FEI Quanta 200F)", "Analytical Instruments", "CRF · Ex Hall", "electron microscopy"),
        ("FE-SEM with EDX (TESCAN)", "Analytical Instruments", "CRF · Block V", "electron microscopy"),
        ("JEOL JSM-7800F FESEM with EDS", "Analytical Instruments", "CRF · Sonipat Campus", "electron microscopy"),
        ("Single-Crystal X-ray Diffraction Facility", "Analytical Instruments", "CRF · IIT Delhi", "xray"),
        ("Physical Property Measurement System", "Analytical Instruments", "CRF · Hauz Khas Campus", "thermal"),
        ("Small-Angle X-ray Scattering Facility", "Analytical Instruments", "CRF · Sonipat Campus", "xray"),
        ("Scanning Tunnelling Microscope", "Analytical Instruments", "CRF · IIT Delhi", "microscopy"),
        ("Photovoltaic EQE/IQE Measurement Facility", "Analytical Instruments", "CRF · Sonipat Campus", "spectroscopy"),
        ("Micro Raman Spectrometer", "Analytical Instruments", "CRF · IIT Delhi", "spectroscopy"),
        ("High-Resolution Mass Spectrometry Facility", "Analytical Instruments", "IIT Delhi · Shared Facility", "spectroscopy"),
        ("Atomic Force Microscope", "Analytical Instruments", "IIT Delhi · Shared Facility", "microscopy"),
        ("High-Resolution X-ray Diffractometer", "Analytical Instruments", "IIT Delhi · Shared Facility", "xray"),
    ],
    "tifr.res.in": [
        ("Bruker 800 MHz Nuclear Magnetic Resonance Spectrometer", "Analytical Instruments", "TIFR · NMR Facility, Colaba", "nmr"),
        ("600 MHz Varian Nuclear Magnetic Resonance Spectrometer", "Analytical Instruments", "TIFR · NMR Facility, Colaba", "nmr"),
        ("Scanning Electron Microscope", "Analytical Instruments", "TIFR · Shared Electron Microscopy Lab", "electron microscopy"),
        ("Transmission Electron Microscope", "Analytical Instruments", "TIFR · Shared Electron Microscopy Lab", "electron microscopy"),
        ("X-ray Diffraction and Compositional Analysis Facility", "Analytical Instruments", "TIFR · Central Research Facilities", "xray"),
        ("Class 1000 Cleanroom and Device Fabrication Facility", "Cleanrooms", "TIFR · Device Fabrication Facility, Colaba", "cleanroom"),
        ("Liquid Helium Liquefier (Linde L280)", "Analytical Instruments", "TIFR · Low Temperature Facility", "thermal"),
        ("Liquid Nitrogen Plant (Stirling STIRLIN-8)", "Analytical Instruments", "TIFR · Low Temperature Facility", "thermal"),
        ("Central Workshop", "Labs", "TIFR · Central Workshop, Colaba", "fabrication"),
        ("High-Performance Computing Facility", "High-Performance Compute", "TIFR · Computing Facility, Colaba", "compute"),
    ],
}


def ensure_owner(institution: Institution) -> User:
    owner = User.query.filter_by(institution_id=institution.id, role=UserRole.owner).first()
    if owner:
        return owner
    email = f"facility.catalog@{institution.domain}"
    owner = User.query.filter_by(email=email).first()
    if owner:
        owner.institution_id = institution.id
        owner.role = UserRole.owner
        return owner
    owner = User(
        name=f"Facility Desk — {institution.name}",
        email=email,
        password_hash=generate_password_hash(secrets.token_urlsafe(32)),
        role=UserRole.owner,
        institution_id=institution.id,
    )
    db.session.add(owner)
    db.session.flush()
    return owner


def main(app=None) -> None:
    app = app or create_app("development")
    with app.app_context():
        institutions = {row.domain: row for row in Institution.query.all()}
        # Remove the requested college and its unused catalog records. Keep
        # pre-existing user accounts, but detach them from the removed campus.
        removed_institution = institutions.get("adgips.ac.in")
        if removed_institution:
            for resource in removed_institution.resources.all():
                if resource.bookings.count() or resource.audit_logs.count():
                    raise RuntimeError(f"Refusing to remove referenced listing: {resource.name}")
                db.session.delete(resource)
            db.session.flush()
            for user in removed_institution.users.all():
                if (
                    user.email == f"facility.catalog@{removed_institution.domain}"
                    and not user.bookings.count()
                    and not user.owned_resources.count()
                    and not user.audit_logs.count()
                ):
                    db.session.delete(user)
                else:
                    user.institution_id = None
            db.session.flush()
            db.session.delete(removed_institution)
            db.session.flush()
            institutions.pop("adgips.ac.in", None)

        expected_domains = set(CATALOG)
        missing = expected_domains - set(institutions)
        if missing:
            raise RuntimeError(f"Institutions missing from catalog selector: {sorted(missing)}")

        # Remove the screenshot listing and unsupported, unused demo listings.
        remove_names = {
            "Formlabs Form 4 Industrial SLA 3D Printer",
            "Illumina NovaSeq X Plus High-Throughput Sequencer",
            "Haas VF-2 5-Axis Precision CNC Machining Centre",
        }
        for resource in Resource.query.filter(Resource.name.in_(remove_names)).all():
            if resource.bookings.count() or resource.audit_logs.count():
                raise RuntimeError(f"Refusing to remove referenced listing: {resource.name}")
            db.session.delete(resource)

        # Preserve historical IDs and logs while correcting details supported
        # by the institutions' public facility catalogs.
        corrections = {
            "Titan Krios G4 300 kV Cryo-TEM": (
                "Titan Themis D3391 Transmission Electron Microscope",
                "IISc CeNSE · Micro and Nano Characterization Facility, Bengaluru",
                "electron microscopy",
            ),
            "JEOL JEM-2100F Field Emission TEM": (
                "Field Emission Gun TEM with STEM, EDS and EELS (300 kV)",
                "IIT Bombay · SAIF, Ground Floor, Room 314, Powai",
                "electron microscopy",
            ),
            "Class 100 ISO 5 Nanofab Cleanroom": (
                "Semiconductor Processing Cleanroom",
                "IISc · Department of Physics, Bengaluru",
                "cleanroom",
            ),
        }
        for old_name, (new_name, location, image_kind) in corrections.items():
            resource = Resource.query.filter_by(name=old_name).first()
            if resource:
                resource.name = new_name
                resource.location = location
                resource.image_url = catalog_photo(image_kind)
                resource.conditions = "Facility access, training and booking are arranged through the institution."

        # This 800 MHz Bruker instrument is listed by TIFR Mumbai, not IIT Bombay.
        nmr = Resource.query.filter_by(name="Bruker 800 MHz Ascend Ultra-Shield NMR").first()
        tifr = institutions["tifr.res.in"]
        if nmr:
            nmr.owner_id = ensure_owner(tifr).id
            nmr.institution_id = tifr.id
            nmr.name = "Bruker 800 MHz Nuclear Magnetic Resonance Spectrometer"
            nmr.location = "TIFR · NMR Facility, Colaba, Mumbai"
            nmr.image_url = catalog_photo("nmr")
            nmr.conditions = "Access and sample requirements are arranged through the TIFR NMR facility."

        owners = {domain: ensure_owner(institution) for domain, institution in institutions.items()}
        added = 0
        for domain, entries in CATALOG.items():
            institution = institutions[domain]
            for index, (name, category_name, location, image_kind) in enumerate(entries):
                resource = Resource.query.filter_by(institution_id=institution.id, name=name).first()
                if resource:
                    resource.image_url = (
                        iisc_catalog_photo(image_kind, index)
                        if domain == "iisc.ac.in"
                        else catalog_photo(image_kind, index)
                    )
                    continue
                category = next(category for category in ResourceCategory if category.value == category_name)
                db.session.add(Resource(
                    owner_id=owners[domain].id,
                    institution_id=institution.id,
                    name=name,
                    category=category,
                    location=location,
                    conditions="Facility access, training and booking are arranged through the institution.",
                    deposit=0,
                    hourly_price=0,
                    is_available=True,
                    image_url=(
                        iisc_catalog_photo(image_kind, index)
                        if domain == "iisc.ac.in"
                        else catalog_photo(image_kind, index)
                    ),
                ))
                added += 1
        db.session.commit()

        print(f"Added {added} verified facility listings.")
        for institution in Institution.query.order_by(Institution.name):
            print(f"{institution.name}: {institution.resources.count()} listings")
        print(f"Total catalog listings: {Resource.query.count()}")


if __name__ == "__main__":
    main()
