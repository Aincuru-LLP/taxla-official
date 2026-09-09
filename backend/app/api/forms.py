"""Customer Requirement Intake Form API.

Public endpoints accessed by the customer via secure token link.
Provides 8-step canonical intake mapped directly to PostgreSQL domain tables
and standard ApplicationRequirement rows for automation snapshot generation.
Supports save draft, resume, and final submission.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db
from app.models.domain import Application, ApplicationRequirement, ApplicationUnit, AuditLog, Client, OfficialAddress
from app.models.state import ApplicationState
from app.services.requirement_engine import RequirementEngine

router = APIRouter(prefix="/forms", tags=["Customer Forms"])


class CustomerFormData(BaseModel):
    # Step 1: Owner Identification
    aadhaar_number: Optional[str] = None
    aadhaar_name: Optional[str] = None
    aadhaar_consent: Optional[bool] = False

    # Step 2: PAN & Organization Details
    organization_type: Optional[str] = "Proprietorship"
    pan_number: Optional[str] = None
    pan_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    social_category: Optional[str] = "General"
    gender: Optional[str] = "Male"
    specially_abled: Optional[bool] = False
    pan_consent: Optional[bool] = False
    itr_status: Optional[str] = "No"  # "Yes" | "No"
    itr_form_type: Optional[str] = None

    # Step 3: Business & Financial Profile
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    enterprise_name: Optional[str] = None
    financial_year: Optional[str] = "2024-25"
    written_down_value: Optional[float] = 0.0
    pollution_control_exclusion: Optional[float] = 0.0
    net_investment: Optional[float] = 0.0
    total_turnover: Optional[float] = 0.0
    export_turnover: Optional[float] = 0.0
    net_domestic_turnover: Optional[float] = 0.0
    enterprise_classification: Optional[str] = "Micro"
    gst_status: Optional[str] = "No"  # "Yes" | "No" | "Exempted"
    gstin: Optional[str] = None

    # Legacy field backwards-compatibility
    itr_filed: Optional[bool] = None
    gst_registered: Optional[bool] = None
    investment_amount: Optional[float] = None
    annual_turnover: Optional[float] = None

    # Step 4: Official Office Address
    flat_door_block: Optional[str] = None
    premises_building: Optional[str] = None
    village_town: Optional[str] = None
    block: Optional[str] = None
    road_street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    pin: Optional[str] = None
    official_mobile: Optional[str] = None
    official_email: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None

    # Step 5: Bank Details & Plant/Unit Locations
    bank_name: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_account_number: Optional[str] = None
    confirm_bank_account_number: Optional[str] = None
    account_holder_name: Optional[str] = None
    has_plant_units: Optional[bool] = False
    units: List[Dict[str, Any]] = Field(default_factory=list)

    # Step 6: Activities & NIC
    major_activity: Optional[str] = "Services"  # "Manufacturing" | "Services" | "Trading"
    business_activity_description: Optional[str] = None
    activities: List[Dict[str, Any]] = Field(default_factory=list)

    # Step 7: Employment & Statutory Registrations
    male_employees: Optional[int] = 0
    female_employees: Optional[int] = 0
    other_employees: Optional[int] = 0
    total_employees: Optional[int] = 0
    interested_in_gem: Optional[bool] = False
    interested_in_treds: Optional[bool] = False
    interested_in_ncs: Optional[bool] = False
    interested_in_nsic_b2b: Optional[bool] = False
    interested_in_skill_india: Optional[bool] = False
    district_industries_centre: Optional[str] = None
    msme_dfo: Optional[str] = None

    # Step 8: Declarations
    declaration_agreed: Optional[bool] = False


@router.get("/{application_code}/{token}")
async def get_customer_form(
    application_code: str,
    token: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch current form data and validation state for customer intake."""
    stmt = (
        select(Application)
        .where(Application.application_number == application_code)
        .options(
            selectinload(Application.client),
            selectinload(Application.official_address),
            selectinload(Application.units),
            selectinload(Application.requirements),
        )
    )
    app = (await db.execute(stmt)).scalars().first()
    if not app:
        try:
            import uuid
            app_uuid = uuid.UUID(application_code)
            app = (
                await db.execute(
                    select(Application)
                    .where(Application.id == app_uuid)
                    .options(
                        selectinload(Application.client),
                        selectinload(Application.official_address),
                        selectinload(Application.units),
                        selectinload(Application.requirements),
                    )
                )
            ).scalars().first()
        except Exception:
            pass

    if not app:
        raise HTTPException(status_code=404, detail="Invalid requirement form link or application code.")

    client = app.client
    addr = app.official_address
    reqs = {r.requirement_key: r.value for r in (app.requirements or []) if r.value}

    # Recover Aadhaar from requirements or client hash if 12 numeric digits
    aadhaar_val = reqs.get("aadhaar") or ""
    if not aadhaar_val and client and client.aadhaar_number_hash:
        clean_h = re.sub(r"\D", "", client.aadhaar_number_hash)
        if len(clean_h) == 12:
            aadhaar_val = clean_h

    # Derived financials
    wdv = float(app.written_down_value or app.net_investment or 0.0)
    exclusions = float(app.eligible_exclusions or 0.0)
    net_inv = max(0.0, float(app.net_investment or (wdv - exclusions)))
    tot_turnover = float(app.total_turnover or 0.0)
    exp_turnover = float(app.export_turnover or 0.0)
    net_turn = max(0.0, float(app.net_turnover or (tot_turnover - exp_turnover)))
    classification = RequirementEngine.calculate_msme_category(net_inv, tot_turnover)

    # ITR and GST status
    itr_status = reqs.get("itr_status") or ("Yes" if reqs.get("itr_filed") == "Yes" else "No")
    itr_form = reqs.get("itr_form_type") or ""
    gst_status = reqs.get("gstin_status") or ("Yes" if reqs.get("gstin_number") else "No")
    gstin_num = reqs.get("gstin_number") or ""

    # DOB / DOI
    dob_str = ""
    if app.incorporation_date:
        dob_str = app.incorporation_date.strftime("%Y-%m-%d")
    elif reqs.get("incorporation_date"):
        dob_str = reqs.get("incorporation_date", "")

    # Parse activities JSON if stored
    activities_list = []
    raw_activities = reqs.get("nic_activities_json")
    if raw_activities:
        try:
            activities_list = json.loads(raw_activities)
        except Exception:
            activities_list = []
    if not activities_list and reqs.get("nic_code"):
        activities_list = [{
            "activity_type": app.major_activity or "Services",
            "nic_5digit": reqs.get("nic_code"),
            "description": reqs.get("business_activity_description") or "",
        }]

    data = {
        "application_code": app.application_number,
        "application_status": app.status,
        "applicant_name": (client.applicant_name or "") if client else "",
        "business_name": (client.business_name or "") if client else "",
        "form_data": {
            # Step 1: Owner Identification
            "aadhaar_number": aadhaar_val,
            "aadhaar_name": (client.applicant_name or reqs.get("aadhaar_name") or "") if client else "",
            "aadhaar_consent": bool(aadhaar_val),

            # Step 2: PAN & Organization Details
            "organization_type": app.enterprise_type or "Proprietorship",
            "pan_number": (client.pan_number or reqs.get("pan") or "") if client else "",
            "pan_name": (reqs.get("pan_name") or (client.applicant_name if client else "")),
            "date_of_birth": dob_str,
            "social_category": (client.social_category or reqs.get("social_category") or "General") if client else "General",
            "gender": (client.gender or reqs.get("gender") or "Male") if client else "Male",
            "specially_abled": (client.divyang_status or reqs.get("divyang") == "Yes") if client else False,
            "pan_consent": bool(client and client.pan_number),
            "itr_status": itr_status,
            "itr_form_type": itr_form,

            # Step 3: Business & Financial Profile
            "mobile_number": (client.mobile_number or reqs.get("mobile") or "") if client else "",
            "email": (client.email or reqs.get("email") or "") if client else "",
            "enterprise_name": (client.business_name or reqs.get("business_name") or "") if client else "",
            "financial_year": reqs.get("financial_year") or "2024-25",
            "written_down_value": wdv,
            "pollution_control_exclusion": exclusions,
            "net_investment": net_inv,
            "total_turnover": tot_turnover,
            "export_turnover": exp_turnover,
            "net_domestic_turnover": net_turn,
            "enterprise_classification": classification,
            "gst_status": gst_status,
            "gstin": gstin_num,
            "itr_filed": itr_status == "Yes",
            "gst_registered": gst_status == "Yes",
            "investment_amount": net_inv,
            "annual_turnover": tot_turnover,

            # Step 4: Official Office Address
            "flat_door_block": (addr.flat or "") if addr else "",
            "premises_building": (addr.building or "") if addr else "",
            "village_town": (addr.village_town or "") if addr else "",
            "block": (addr.block or "") if addr else "",
            "road_street": (addr.road_street or "") if addr else "",
            "city": (addr.city or "") if addr else "",
            "state": (addr.state or "") if addr else "",
            "district": (addr.district or "") if addr else "",
            "pin": (addr.pin or "") if addr else "",
            "official_mobile": reqs.get("official_mobile") or ((client.mobile_number or "") if client else ""),
            "official_email": reqs.get("official_email") or ((client.email or "") if client else ""),
            "latitude": reqs.get("latitude") or "",
            "longitude": reqs.get("longitude") or "",

            # Step 5: Bank Details & Plant/Unit Locations
            "bank_name": app.bank_name or "",
            "bank_ifsc": app.bank_ifsc or "",
            "bank_account_number": app.bank_account_number or "",
            "confirm_bank_account_number": app.bank_account_number or "",
            "account_holder_name": (client.applicant_name or "") if client else "",
            "has_plant_units": bool(app.units and len(app.units) > 0),
            "units": [
                {
                    "unit_name": u.unit_name or "",
                    "flat": u.flat or "",
                    "building": u.building or "",
                    "village_town": u.village_town or "",
                    "block": u.block or "",
                    "road_street": u.road_street or "",
                    "city": u.city or "",
                    "state": u.state or "",
                    "district": u.district or "",
                    "pin": u.pin or "",
                }
                for u in (app.units or [])
            ],

            # Step 6: Major Activity & Products (NIC)
            "major_activity": app.major_activity or "Services",
            "business_activity_description": reqs.get("business_activity_description") or "",
            "activities": activities_list,

            # Step 7: Employment & Statutory Registrations
            "male_employees": app.male_employees or 0,
            "female_employees": app.female_employees or 0,
            "other_employees": app.other_employees or 0,
            "total_employees": (app.male_employees or 0) + (app.female_employees or 0) + (app.other_employees or 0),
            "interested_in_gem": app.interested_in_gem or False,
            "interested_in_treds": app.interested_in_treds or False,
            "interested_in_ncs": app.interested_in_ncs or False,
            "interested_in_nsic_b2b": app.interested_in_nsic_b2b or False,
            "interested_in_skill_india": reqs.get("skill_india_interest") == "Yes",
            "district_industries_centre": app.district_industries_centre or "",
            "msme_dfo": reqs.get("msme_dfo") or "",

            # Step 8: Declarations
            "declaration_agreed": reqs.get("declaration") == "Yes",
        },
    }

    return data


async def _save_address_and_units(app: Application, payload: CustomerFormData, db: AsyncSession) -> None:
    """Save official address and plant units from customer payload."""
    if not app.official_address:
        app.official_address = OfficialAddress(application_id=app.id)

    if payload.flat_door_block is not None:
        app.official_address.flat = payload.flat_door_block
    if payload.premises_building is not None:
        app.official_address.building = payload.premises_building
    if payload.village_town is not None:
        app.official_address.village_town = payload.village_town
    if payload.block is not None:
        app.official_address.block = payload.block
    if payload.road_street is not None:
        app.official_address.road_street = payload.road_street
    if payload.city is not None:
        app.official_address.city = payload.city
    if payload.state is not None:
        app.official_address.state = payload.state
    if payload.district is not None:
        app.official_address.district = payload.district
    if payload.pin is not None:
        app.official_address.pin = payload.pin

    db.add(app.official_address)

    # Save units if provided
    if payload.has_plant_units and payload.units:
        for u in (app.units or []):
            await db.delete(u)
        app.units.clear()
        for u_data in payload.units:
            unit = ApplicationUnit(
                application_id=app.id,
                unit_name=u_data.get("unit_name") or payload.enterprise_name or "Unit 1",
                flat=u_data.get("flat") or payload.flat_door_block or "",
                building=u_data.get("building") or payload.premises_building or "",
                village_town=u_data.get("village_town") or payload.village_town or "",
                block=u_data.get("block") or payload.block or "",
                road_street=u_data.get("road_street") or payload.road_street or "",
                city=u_data.get("city") or payload.city or "",
                state=u_data.get("state") or payload.state or "",
                district=u_data.get("district") or payload.district or "",
                pin=u_data.get("pin") or payload.pin or "",
            )
            db.add(unit)
    elif payload.city or payload.state:
        # Default single unit mirroring official address
        if not app.units:
            unit = ApplicationUnit(
                application_id=app.id,
                unit_name=payload.enterprise_name or (app.client.business_name if app.client else "Main Unit"),
                flat=payload.flat_door_block or "",
                building=payload.premises_building or "",
                village_town=payload.village_town or "",
                block=payload.block or "",
                road_street=payload.road_street or "",
                city=payload.city or "",
                state=payload.state or "",
                district=payload.district or "",
                pin=payload.pin or "",
            )
            db.add(unit)


async def _sync_requirements_from_form(app: Application, payload: CustomerFormData, db: AsyncSession) -> None:
    """Synchronize submitted customer form values with standard ApplicationRequirement rows."""
    reqs_res = await db.execute(
        select(ApplicationRequirement).where(ApplicationRequirement.application_id == app.id)
    )
    reqs = {r.requirement_key: r for r in reqs_res.scalars().all()}
    if not reqs:
        await RequirementEngine.initialize_application_requirements(app.id, db)
        reqs_res = await db.execute(
            select(ApplicationRequirement).where(ApplicationRequirement.application_id == app.id)
        )
        reqs = {r.requirement_key: r for r in reqs_res.scalars().all()}

    full_addr = " ".join(
        p for p in [
            payload.flat_door_block,
            payload.premises_building,
            payload.road_street,
            payload.village_town,
            payload.block,
            payload.city,
            payload.district,
            payload.state,
            payload.pin,
        ] if p
    ).strip()

    # Calculate net investment & net turnover
    wdv = float(payload.written_down_value or payload.investment_amount or 0.0)
    exclusions = float(payload.pollution_control_exclusion or 0.0)
    net_inv = max(0.0, wdv - exclusions)

    tot_turnover = float(payload.total_turnover or payload.annual_turnover or 0.0)
    exp_turnover = float(payload.export_turnover or 0.0)
    net_turn = max(0.0, tot_turnover - exp_turnover)

    # First NIC code from activities list
    first_nic_code = ""
    if payload.activities:
        for act in payload.activities:
            c = act.get("nic_5digit") or act.get("nic_code") or ""
            if c:
                first_nic_code = c
                break

    mapping = {
        "aadhaar": (payload.aadhaar_number, bool(payload.aadhaar_number)),
        "aadhaar_name": (payload.aadhaar_name, bool(payload.aadhaar_name)),
        "pan": (payload.pan_number, bool(payload.pan_number)),
        "pan_name": (payload.pan_name, bool(payload.pan_name)),
        "mobile": (payload.mobile_number, bool(payload.mobile_number)),
        "email": (payload.email, bool(payload.email)),
        "social_category": (payload.social_category or "General", True),
        "gender": (payload.gender or "Male", True),
        "divyang": ("Yes" if payload.specially_abled else "No", True),
        "business_name": (payload.enterprise_name, bool(payload.enterprise_name)),
        "official_address": (full_addr, bool(payload.city and payload.state and payload.pin)),
        "plant_units": (f"Units: {len(payload.units)} registered" if payload.units else f"Unit 1: {payload.city}, {payload.state}", bool(payload.city or payload.units)),
        "bank_info": (f"{payload.bank_name} A/C: {payload.bank_account_number} IFSC: {payload.bank_ifsc}" if payload.bank_name else "", bool(payload.bank_name and payload.bank_account_number and payload.bank_ifsc)),
        "business_activity": (payload.major_activity or "Services", bool(payload.major_activity)),
        "business_activity_description": (payload.business_activity_description or "", bool(payload.business_activity_description)),
        "nic_code": (first_nic_code, bool(first_nic_code)),
        "nic_activities_json": (json.dumps(payload.activities) if payload.activities else "", bool(payload.activities)),
        "employment": (f"Male: {payload.male_employees or 0}, Female: {payload.female_employees or 0}, Other: {payload.other_employees or 0}", True),
        "investment": (str(net_inv), True),
        "turnover": (str(tot_turnover), True),
        "child_labour_declaration": ("Yes", True),
        "declaration": ("Yes" if payload.declaration_agreed else "No", bool(payload.declaration_agreed)),
        "gem_interest": ("Yes" if payload.interested_in_gem else "No", True),
        "treds_interest": ("Yes" if payload.interested_in_treds else "No", True),
        "ncs_interest": ("Yes" if payload.interested_in_ncs else "No", True),
        "nsic_interest": ("Yes" if payload.interested_in_nsic_b2b else "No", True),
        "skill_india_interest": ("Yes" if payload.interested_in_skill_india else "No", True),
        "gstin_status": (payload.gst_status or ("Yes" if payload.gst_registered else "No"), True),
        "gstin_number": (payload.gstin or "", bool(payload.gstin)),
        "itr_status": (payload.itr_status or ("Yes" if payload.itr_filed else "No"), True),
        "itr_form_type": (payload.itr_form_type or "", bool(payload.itr_form_type)),
        "official_mobile": (payload.official_mobile or payload.mobile_number or "", bool(payload.official_mobile or payload.mobile_number)),
        "official_email": (payload.official_email or payload.email or "", bool(payload.official_email or payload.email)),
        "latitude": (payload.latitude or "", bool(payload.latitude)),
        "longitude": (payload.longitude or "", bool(payload.longitude)),
        "financial_year": (payload.financial_year or "2024-25", True),
        "msme_dfo": (payload.msme_dfo or "", bool(payload.msme_dfo)),
    }

    for key, (val, completed) in mapping.items():
        if key in reqs:
            req = reqs[key]
            if val is not None:
                req.value = str(val)
            req.is_completed = completed
            req.source = "USER_PROVIDED"
            req.validation_status = "VALID" if completed else "PENDING"
            db.add(req)
        else:
            # Dynamic requirement field (e.g. gstin_status, skill_india_interest)
            req = ApplicationRequirement(
                application_id=app.id,
                requirement_key=key,
                display_label=key.replace("_", " ").title(),
                category="USER_FORM",
                is_required=False,
                is_completed=completed,
                source="USER_PROVIDED",
                value=str(val) if val is not None else "",
                validation_status="VALID" if completed else "PENDING",
            )
            db.add(req)

    await RequirementEngine.recalculate_completion(app.id, db)


def _apply_payload_to_entities(app: Application, payload: CustomerFormData) -> None:
    """Update Application and Client attributes with validated payload."""
    if app.client:
        if payload.aadhaar_name:
            app.client.applicant_name = payload.aadhaar_name
        if payload.pan_number:
            app.client.pan_number = payload.pan_number
        if payload.enterprise_name:
            app.client.business_name = payload.enterprise_name
        if payload.mobile_number:
            app.client.mobile_number = payload.mobile_number
        if payload.email:
            app.client.email = payload.email
        if payload.gender:
            app.client.gender = payload.gender
        if payload.social_category:
            app.client.social_category = payload.social_category
        if payload.specially_abled is not None:
            app.client.divyang_status = payload.specially_abled
        if payload.aadhaar_number:
            clean_digits = re.sub(r"\D", "", payload.aadhaar_number)
            if len(clean_digits) == 12:
                app.client.aadhaar_number_hash = clean_digits

    # Financials calculations
    wdv = payload.written_down_value if payload.written_down_value is not None else (payload.investment_amount or 0.0)
    exclusions = payload.pollution_control_exclusion or 0.0
    net_inv = max(0.0, float(wdv) - float(exclusions))
    tot_turn = payload.total_turnover if payload.total_turnover is not None else (payload.annual_turnover or 0.0)
    exp_turn = payload.export_turnover or 0.0
    net_turn = max(0.0, float(tot_turn) - float(exp_turn))

    app.written_down_value = wdv
    app.eligible_exclusions = exclusions
    app.net_investment = net_inv
    app.total_turnover = tot_turn
    app.export_turnover = exp_turn
    app.net_turnover = net_turn

    # Bank
    if payload.bank_name is not None:
        app.bank_name = payload.bank_name
    if payload.bank_ifsc is not None:
        app.bank_ifsc = payload.bank_ifsc.upper()
    if payload.bank_account_number is not None:
        app.bank_account_number = payload.bank_account_number

    # Business & Activities
    if payload.major_activity:
        app.major_activity = payload.major_activity
    if payload.organization_type:
        app.enterprise_type = payload.organization_type
    if payload.date_of_birth:
        try:
            app.incorporation_date = datetime.strptime(payload.date_of_birth, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass

    # Employment
    if payload.male_employees is not None:
        app.male_employees = payload.male_employees
    if payload.female_employees is not None:
        app.female_employees = payload.female_employees
    if payload.other_employees is not None:
        app.other_employees = payload.other_employees

    # Statutory Portals
    if payload.interested_in_gem is not None:
        app.interested_in_gem = payload.interested_in_gem
    if payload.interested_in_treds is not None:
        app.interested_in_treds = payload.interested_in_treds
    if payload.interested_in_ncs is not None:
        app.interested_in_ncs = payload.interested_in_ncs
    if payload.interested_in_nsic_b2b is not None:
        app.interested_in_nsic_b2b = payload.interested_in_nsic_b2b
    if payload.district_industries_centre is not None:
        app.district_industries_centre = payload.district_industries_centre


@router.patch("/{application_code}/{token}")
async def save_customer_form_draft(
    application_code: str,
    token: str,
    payload: CustomerFormData,
    db: AsyncSession = Depends(get_async_db),
):
    """Auto-save customer intake draft without state transition."""
    stmt = (
        select(Application)
        .where(Application.application_number == application_code)
        .options(
            selectinload(Application.client),
            selectinload(Application.official_address),
            selectinload(Application.units),
            selectinload(Application.requirements),
        )
    )
    app = (await db.execute(stmt)).scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    _apply_payload_to_entities(app, payload)
    await _save_address_and_units(app, payload, db)
    await _sync_requirements_from_form(app, payload, db)

    db.add(app)
    if app.client:
        db.add(app.client)
    await db.commit()

    return {"success": True, "message": "Draft saved successfully."}


@router.post("/{application_code}/{token}/submit")
async def submit_customer_form(
    application_code: str,
    token: str,
    payload: CustomerFormData,
    db: AsyncSession = Depends(get_async_db),
):
    """Customer submits complete requirement form.

    Transitions application to FORM_SUBMITTED or preserves READY_FOR_PORTAL,
    saves address, units, client info, and updates requirements checklist.
    """
    stmt = (
        select(Application)
        .where(Application.application_number == application_code)
        .options(
            selectinload(Application.client),
            selectinload(Application.official_address),
            selectinload(Application.units),
            selectinload(Application.requirements),
        )
    )
    app = (await db.execute(stmt)).scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Validate minimal required fields across domains
    if not payload.aadhaar_name or not payload.pan_number:
        raise HTTPException(status_code=400, detail="Owner Name and PAN are required for submission.")

    # Strict format validation — reject bad data at intake, never let it reach automation
    if payload.aadhaar_number:
        aadhaar_digits = re.sub(r"\D", "", payload.aadhaar_number)
        if len(aadhaar_digits) != 12:
            raise HTTPException(status_code=400, detail="Aadhaar Number must be exactly 12 numeric digits.")
        payload.aadhaar_number = aadhaar_digits

    if payload.pan_number:
        clean_pan = payload.pan_number.strip().upper()
        if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", clean_pan):
            raise HTTPException(
                status_code=400,
                detail="PAN must match standard format ABCDE1234F (5 letters, 4 digits, 1 letter)."
            )
        payload.pan_number = clean_pan

    # Validate financial consistency
    if (payload.export_turnover or 0.0) > (payload.total_turnover or payload.annual_turnover or 0.0):
        raise HTTPException(
            status_code=400,
            detail="Export turnover cannot exceed total turnover."
        )

    # Validate bank account confirmation if provided
    if (
        payload.confirm_bank_account_number
        and payload.bank_account_number
        and payload.confirm_bank_account_number != payload.bank_account_number
    ):
        raise HTTPException(status_code=400, detail="Bank Account Numbers do not match.")

    # Apply submitted fields to client & application
    _apply_payload_to_entities(app, payload)
    await _save_address_and_units(app, payload, db)
    await _sync_requirements_from_form(app, payload, db)

    # Transition application status: advance to FORM_SUBMITTED or preserve READY_FOR_PORTAL
    if app.status in ("READY_FOR_PORTAL", "READY_FOR_AUTOMATION", "PAYMENT_COMPLETED"):
        app.status = "READY_FOR_PORTAL"
    else:
        app.status = (
            ApplicationState.FORM_SUBMITTED.value
            if hasattr(ApplicationState, "FORM_SUBMITTED")
            else "FORM_SUBMITTED"
        )

    db.add(app)
    if app.client:
        db.add(app.client)

    # Record audit log
    audit = AuditLog(
        application_id=app.id,
        action="FORM_SUBMITTED_BY_CUSTOMER",
        metadata_json={
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "applicant": payload.aadhaar_name,
            "pan": payload.pan_number,
            "enterprise": payload.enterprise_name,
        },
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "application_code": app.application_number,
        "status": app.status,
        "message": "Your requirements have been submitted successfully. Our team is now reviewing your application.",
    }

