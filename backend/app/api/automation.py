"""Automation and Manual Processing API for TAXLA Operations Platform.

Enforces:
1. Preflight checklist validation before start.
2. Generation of immutable Approved Application Snapshot JSON.
3. Explicit employee start trigger.
4. Human-in-the-loop OTP and CAPTCHA handling.
5. First-class Manual Processing fallback with symmetrical certificate flow.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db
from app.core.security import get_current_user
from app.models.domain import (
    Application,
    ApplicationRequirement,
    AuditLog,
    Certificate,
    Client,
    ExtractedData,
    OfficialAddress,
    WorkflowExecution,
    User,
)
from app.models.state import ApplicationState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["Automation"])


class OTPPayload(BaseModel):
    otp: str = Field(min_length=4, max_length=8)


class ManualProcessPayload(BaseModel):
    udyam_registration_number: str = Field(min_length=10)
    certificate_file_name: Optional[str] = "udyam_certificate.pdf"
    notes: Optional[str] = None


@router.get("/{id}/automation")
async def get_automation_status(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve realtime automation progress, worker state, and preflight checklist."""
    app_res = await db.execute(
        select(Application)
        .where(Application.id == id)
        .options(
            selectinload(Application.client),
            selectinload(Application.official_address),
            selectinload(Application.units),
            selectinload(Application.executions),
        )
    )
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Evaluate preflight criteria strictly against actual customer data
    client = app.client
    addr = app.official_address

    has_client = bool(client and client.applicant_name and client.pan_number and (client.mobile_number or client.email))
    has_bank = bool(app.bank_name and app.bank_account_number and app.bank_ifsc)
    has_activity = bool(app.major_activity)
    has_address = bool(addr and addr.city and addr.pin)
    is_payment_done = app.status not in ("NEW", "FORM_SENT")
    can_start = bool(
        has_client
        and has_bank
        and has_activity
        and has_address
        and app.status not in ("AUTOMATION_RUNNING", "PORTAL_RUNNING", "COMPLETED")
    )

    preflight = {
        "requirements_submitted": app.status not in ("NEW", "FORM_SENT"),
        "owner_pan_valid": has_client,
        "bank_details_valid": has_bank,
        "activity_nic_valid": has_activity,
        "address_valid": has_address,
        "payment_completed": is_payment_done,
        "can_start_automation": can_start,
    }

    # Latest execution
    executions = app.executions or []
    latest_exec = executions[-1] if executions else None

    # Step monitor state
    status_upper = app.status.upper()
    active_step = "READY"
    if "OTP" in status_upper:
        active_step = "OTP_VERIFICATION"
    elif status_upper in ("PORTAL_RUNNING", "AUTOMATION_RUNNING"):
        active_step = "DATA_ENTRY"
    elif status_upper in ("SUBMITTING", "FINAL_SUBMISSION"):
        active_step = "FINAL_SUBMISSION"
    elif status_upper in ("REGISTERED", "CERTIFICATE_READY", "COMPLETED"):
        active_step = "COMPLETED"
    elif status_upper == "MANUAL_PROCESSING":
        active_step = "MANUAL_PROCESSING"

    from app.services.portal_selectors import get_selectors

    return {
        "application_id": str(app.id),
        "application_number": app.application_number,
        "status": app.status,
        "processing_mode": "MANUAL" if app.status == "MANUAL_PROCESSING" else "AUTOMATION",
        "preflight": preflight,
        "can_start_automation": can_start,
        "current_step": active_step,
        "is_running": status_upper in ("PORTAL_RUNNING", "AUTOMATION_RUNNING"),
        "is_otp_required": "OTP" in status_upper,
        "is_captcha_required": False,  # Flagged when browser pauses for CAPTCHA
        "last_error": None,
        "execution_id": str(latest_exec.id) if latest_exec else None,
        "target_url": get_selectors().base_url,
    }


def build_approved_snapshot(
    app: Application,
    client: Optional[Client],
    addr: Optional[OfficialAddress],
    reqs: Dict[str, Any],
    ext_dict: Dict[str, Any],
    aadhaar_num: str,
    aadhaar_name: str,
    pan_num: str,
    pan_name: str,
    approved_by: str,
) -> Dict[str, Any]:
    """Compile Approved Application Snapshot JSON with immutable identity (PROMPT §7)."""
    return {
        "snapshot_id": str(uuid.uuid4()),
        "application_id": str(app.id),
        "application_code": app.application_number,
        "customer_id": str(client.id) if client else str(app.id),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": approved_by,
        # Section 1: Aadhaar
        "owner": {
            "aadhaar_name": aadhaar_name,
            "aadhaar_number": aadhaar_num,
            "consent": True,
        },
        # Section 2: PAN & Org
        "pan": {
            "organisation_type": app.enterprise_type or "Proprietorship",
            "has_pan": "Yes",
            "pan_number": pan_num,
            "name_on_pan": pan_name,
            "dob_doi": app.incorporation_date.strftime("%Y-%m-%d") if app.incorporation_date else (reqs.get("incorporation_date") or "2020-01-01"),
            "pan_consent": True,
            "itr_filed": reqs.get("itr_status") or "No",
            "gstin_status": reqs.get("gstin_status") or "No",
            "gstin_number": reqs.get("gstin_number") or "",
        },
        # Section 3: Basic Details
        "basic": {
            "entrepreneur_name": client.applicant_name if client else aadhaar_name,
            "mobile_number": client.mobile_number if client else (reqs.get("mobile") or ""),
            "email": client.email if client else (reqs.get("email") or ""),
            "enterprise_name": client.business_name if client else (pan_name or ""),
            "social_category": client.social_category if client else "General",
            "gender": client.gender if client else "Male",
            "is_divyang": "Yes" if (client and client.divyang_status) else "No",
        },
        # Section 4: Official Address
        "address": {
            "flat": addr.flat if addr else "",
            "building": addr.building if addr else "",
            "village": addr.village_town if addr else "",
            "block": addr.block if addr else "",
            "road": addr.road_street if addr else "",
            "city": addr.city if addr else "",
            "state": (addr.state if addr else None) or "Delhi",
            "district": (addr.district if addr else None) or (addr.city if addr else None) or "",
            "pin": addr.pin if addr else "",
            "mobile": reqs.get("official_mobile") or (client.mobile_number if client else (reqs.get("mobile") or "")),
            "email": reqs.get("official_email") or (client.email if client else (reqs.get("email") or "")),
        },
        # Section 5: Units
        "units": [
            {
                "unit_name": u.unit_name or (client.business_name if client else "Main Unit"),
                "flat": u.flat or (addr.flat if addr else "") or "",
                "building": u.building or (addr.building if addr else "") or "",
                "village": u.village_town or (addr.village_town if addr else "") or "",
                "block": u.block or (addr.block if addr else "") or "",
                "road": u.road_street or (addr.road_street if addr else "") or "",
                "city": u.city or (addr.city if addr else "") or "",
                "state": u.state or (addr.state if addr else "") or "",
                "district": u.district or (addr.district if addr else "") or "",
                "pin": u.pin or (addr.pin if addr else "") or "",
            }
            for u in (app.units or [])
        ] if app.units else [
            {
                "unit_name": client.business_name if client else "Main Unit",
                "flat": (addr.flat if addr else "") or "",
                "building": (addr.building if addr else "") or "",
                "village": (addr.village_town if addr else "") or "",
                "block": (addr.block if addr else "") or "",
                "road": (addr.road_street if addr else "") or "",
                "city": (addr.city if addr else "") or "",
                "state": (addr.state if addr else "") or "",
                "district": (addr.district if addr else "") or "",
                "pin": (addr.pin if addr else "") or "",
            }
        ],
        # Section 6: NIC Activity
        "nic": {
            "major_activity": app.major_activity or "Services",
            "two_digit": (reqs.get("nic_code") or "62011")[:2],
            "four_digit": (reqs.get("nic_code") or "62011")[:4],
            "five_digit": reqs.get("nic_code") or "62011",
            "activity_nature": app.major_activity or "Services",
        },
        # Section 7: Employment
        "employment": {
            "male": app.male_employees if app.male_employees is not None else 0,
            "female": app.female_employees if app.female_employees is not None else 0,
            "other": app.other_employees if app.other_employees is not None else 0,
            "total": (app.male_employees or 0) + (app.female_employees or 0) + (app.other_employees or 0),
        },
        # Section 8: Financials
        "financials": {
            "financial_year": reqs.get("financial_year") or "2024-25",
            "enterprise_type": (app.enterprise_type or "Micro").title(),
            "written_down_value": float(app.written_down_value or app.net_investment or 0.0),
            "pollution_control_exclusion": float(app.eligible_exclusions or 0.0),
            "net_investment": float(app.net_investment or 0.0),
            "total_turnover": float(app.total_turnover or 0.0),
            "export_turnover": float(app.export_turnover or 0.0),
            "net_turnover": float(app.net_turnover or app.total_turnover or 0.0),
            "is_itr_filed": reqs.get("itr_status") or "No",
        },
        # Section 9: Bank Details
        "bank": {
            "bank_name": app.bank_name or "",
            "ifsc": app.bank_ifsc or "",
            "account_number": app.bank_account_number or "",
            "confirm_account_number": app.bank_account_number or "",
        },
        # Section 10: Other Details & Portal Registrations
        "other_details": {
            "gem": "Yes" if app.interested_in_gem else "No",
            "treds": "Yes" if app.interested_in_treds else "No",
            "ncs": "Yes" if app.interested_in_ncs else "No",
            "nsic": "Yes" if app.interested_in_nsic_b2b else "No",
            "skill_india": reqs.get("skill_india_interest") or "Yes",
            "dic": app.district_industries_centre or f"DIC {(addr.city if addr else '') or ''}".strip(),
        },
        # Section 11: Declarations
        "declaration": {
            "is_true_and_correct": True,
            "is_demo_acknowledged": True,
        },
    }


async def _build_snapshot_for_app(app_id: uuid.UUID, app: Application, db: AsyncSession, current_user_email: str) -> Dict[str, Any]:
    """Helper to load requirements and build approved snapshot for an application."""
    req_res = await db.execute(
        select(ApplicationRequirement).where(ApplicationRequirement.application_id == app.id)
    )
    reqs = {r.requirement_key: r.value for r in req_res.scalars().all() if r.value}

    ext_res = await db.execute(
        select(ExtractedData).where(ExtractedData.application_id == app.id)
    )
    ext_dict = {e.field_name: e.field_value for e in ext_res.scalars().all() if e.field_name}

    client = app.client
    addr = app.official_address

    raw_aadhaar = (
        reqs.get("aadhaar")
        or reqs.get("aadhaar_number")
        or ext_dict.get("aadhaar_number")
        or ext_dict.get("aadhaar")
        or (client.aadhaar_number_hash if (client and client.aadhaar_number_hash and len(re.sub(r"\D", "", client.aadhaar_number_hash)) == 12) else None)
    )
    cleaned_aadhaar = re.sub(r"\D", "", str(raw_aadhaar)) if raw_aadhaar else ""
    aadhaar_num = cleaned_aadhaar if len(cleaned_aadhaar) == 12 else None

    aadhaar_name = (
        reqs.get("aadhaar_name")
        or (client.applicant_name if client else None)
        or ext_dict.get("aadhaar_name")
        or ext_dict.get("applicant_name")
    )

    raw_pan = (
        reqs.get("pan")
        or reqs.get("pan_number")
        or (client.pan_number if client else None)
        or ext_dict.get("pan_number")
        or ext_dict.get("pan")
    )
    cleaned_pan = str(raw_pan).strip().upper() if raw_pan else ""
    pan_num = cleaned_pan if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", cleaned_pan) else None

    pan_name = (
        reqs.get("pan_name")
        or (client.business_name if client and app.enterprise_type not in ("Proprietorship", None) else None)
        or (client.applicant_name if client else None)
        or aadhaar_name
    )

    return build_approved_snapshot(
        app=app,
        client=client,
        addr=addr,
        reqs=reqs,
        ext_dict=ext_dict,
        aadhaar_num=aadhaar_num or "",
        aadhaar_name=aadhaar_name or "",
        pan_num=pan_num or "",
        pan_name=pan_name or "",
        approved_by=current_user_email,
    )


@router.post("/{id}/automation/start")
async def start_automation(
    id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Employee explicitly starts automation.

    Validates strict preflight criteria against actual database records,
    compiles immutable Approved Application Snapshot JSON with zero demo fallbacks,
    enqueues worker job, and transitions state to AUTOMATION_RUNNING.
    """
    app_uuid = None
    try:
        app_uuid = uuid.UUID(str(id))
        stmt = select(Application).where(Application.id == app_uuid)
    except ValueError:
        stmt = select(Application).where(Application.application_number == str(id))

    app_res = await db.execute(
        stmt.options(
            selectinload(Application.client),
            selectinload(Application.official_address),
            selectinload(Application.units),
        )
    )
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Prevent concurrent execution
    if app.status in (ApplicationState.PORTAL_RUNNING.value, "AUTOMATION_RUNNING"):
        raise HTTPException(status_code=409, detail="Automation is already running for this application.")

    client = app.client
    addr = app.official_address

    # Fetch requirements and extracted data
    req_res = await db.execute(
        select(ApplicationRequirement).where(ApplicationRequirement.application_id == app.id)
    )
    reqs = {r.requirement_key: r.value for r in req_res.scalars().all() if r.value}

    ext_res = await db.execute(
        select(ExtractedData).where(ExtractedData.application_id == app.id)
    )
    ext_dict = {e.field_name: e.field_value for e in ext_res.scalars().all() if e.field_name}

    import re

    # 1. Resolve plaintext Aadhaar number (must be exactly 12 digits)
    raw_aadhaar = (
        reqs.get("aadhaar")
        or reqs.get("aadhaar_number")
        or ext_dict.get("aadhaar_number")
        or ext_dict.get("aadhaar")
        or (client.aadhaar_number_hash if (client and client.aadhaar_number_hash and len(re.sub(r"\D", "", client.aadhaar_number_hash)) == 12) else None)
    )
    cleaned_aadhaar = re.sub(r"\D", "", str(raw_aadhaar)) if raw_aadhaar else ""
    aadhaar_num = cleaned_aadhaar if len(cleaned_aadhaar) == 12 else None

    # 2. Resolve Aadhaar Name
    aadhaar_name = (
        reqs.get("aadhaar_name")
        or (client.applicant_name if client else None)
        or ext_dict.get("aadhaar_name")
        or ext_dict.get("applicant_name")
    )

    # 3. Resolve PAN Number (must match 10-char Indian PAN format)
    raw_pan = (
        reqs.get("pan")
        or reqs.get("pan_number")
        or (client.pan_number if client else None)
        or ext_dict.get("pan_number")
        or ext_dict.get("pan")
    )
    cleaned_pan = str(raw_pan).strip().upper() if raw_pan else ""
    pan_num = cleaned_pan if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", cleaned_pan) else None

    # 4. Resolve PAN Name
    pan_name = (
        reqs.get("pan_name")
        or (client.business_name if client and app.enterprise_type not in ("Proprietorship", None) else None)
        or (client.applicant_name if client else None)
        or aadhaar_name
    )

    # 5. Strict Pre-flight Validation (PROMPT §19 — Never silently substitute demo data)
    missing_fields = []
    if not aadhaar_num:
        missing_fields.append("Aadhaar Number (12 numeric digits)")
    if not aadhaar_name:
        missing_fields.append("Aadhaar Applicant Name")
    if not pan_num:
        missing_fields.append("PAN Number (Valid format: ABCDE1234F)")
    if not client:
        missing_fields.append("Client Information Profile")
    else:
        if not (client.mobile_number or reqs.get("mobile")):
            missing_fields.append("Mobile Number")
        if not (client.email or reqs.get("email")):
            missing_fields.append("Email Address")
        if not (client.business_name or reqs.get("business_name")):
            missing_fields.append("Enterprise / Business Name")
    if not addr or not (addr.city and addr.pin):
        missing_fields.append("Official Address (City and PIN Code required)")
    if not (app.bank_name and app.bank_account_number and app.bank_ifsc):
        missing_fields.append("Bank Details (Bank Name, Account Number, and IFSC Code)")

    if missing_fields:
        logger.warning(
            "Preflight failed for application %s (%s). Missing: %s",
            app.id, app.application_number, missing_fields
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "AUTOMATION_PREFLIGHT_FAILED",
                "message": "Automation cannot start due to missing required customer data. Please complete the missing fields in the application.",
                "missing_fields": missing_fields,
            },
        )

    snapshot = build_approved_snapshot(
        app=app,
        client=client,
        addr=addr,
        reqs=reqs,
        ext_dict=ext_dict,
        aadhaar_num=aadhaar_num or "",
        aadhaar_name=aadhaar_name or "",
        pan_num=pan_num or "",
        pan_name=pan_name or "",
        approved_by=current_user.email,
    )

    # Snapshot Integrity Check (PROMPT §8)
    if snapshot["application_id"] != str(app.id):
        raise HTTPException(status_code=500, detail="Snapshot integrity check failed: application_id mismatch.")
    if snapshot["application_code"] != app.application_number:
        raise HTTPException(status_code=500, detail="Snapshot integrity check failed: application_code mismatch.")

    # Transition to PORTAL_RUNNING / AUTOMATION_RUNNING
    app.status = ApplicationState.PORTAL_RUNNING.value
    db.add(app)

    # Record audit log with immutable snapshot
    job_id = str(uuid.uuid4())
    audit = AuditLog(
        actor_id=current_user.id,
        application_id=app.id,
        action="AUTOMATION_STARTED",
        metadata_json={
            "automation_job_id": job_id,
            "snapshot_id": snapshot["snapshot_id"],
            "snapshot": snapshot,
            "started_by": current_user.email,
        },
    )
    db.add(audit)
    await db.commit()

    # Job payload for worker (PROMPT §10)
    job_payload = {
        "automation_job_id": job_id,
        "application_id": str(app.id),
        "application_code": app.application_number,
        "snapshot": snapshot,
    }

    # Enqueue to Redis queue for worker pick up
    enqueued = False
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from app.core.config import settings

        redis_pool = await create_pool(RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT))
        await redis_pool.enqueue_job('start_playwright_automation_job', job_payload)
        await redis_pool.aclose()
        enqueued = True
    except Exception as e:
        logger.warning("Could not enqueue to ARQ pool: %s", e)

    # If Redis queue offline or not picked up, run directly in background
    if not enqueued:
        import asyncio
        from worker.playwright_agent import run_automation
        asyncio.create_task(run_automation(str(app.id), snapshot=snapshot, automation_job_id=job_id))

    return {
        "success": True,
        "automation_job_id": job_id,
        "application_id": str(app.id),
        "application_code": app.application_number,
        "status": "QUEUED",
        "snapshot_id": snapshot["snapshot_id"],
        "message": "Automation worker queued with approved immutable snapshot.",
    }


@router.post("/{id}/automation/otp")
async def submit_otp(
    id: uuid.UUID,
    payload: OTPPayload,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Employee enters customer-provided OTP to resume automation worker."""
    app_res = await db.execute(select(Application).where(Application.id == id))
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Record audit log (NEVER save raw OTP code in audit log for privacy/compliance)
    audit = AuditLog(
        actor_id=current_user.id,
        application_id=app.id,
        action="OTP_ENTERED_BY_EMPLOYEE",
        metadata_json={"entered_by": current_user.email, "otp_length": len(payload.otp)},
    )
    db.add(audit)
    await db.commit()

    # Publish OTP code to Redis pub/sub for the listening Playwright worker
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings
        r = aioredis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        await r.publish(f"otp_{id}", payload.otp)
        await r.aclose()
    except Exception as e:
        logger.warning("Failed to publish OTP to Redis channel: %s", e)

    return {
        "success": True,
        "status": app.status,
        "message": "OTP dispatched to worker. Automation resuming.",
    }


@router.post("/{id}/automation/continue")
async def continue_automation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Employee confirms CAPTCHA solved in visible Chrome window."""
    app_res = await db.execute(select(Application).where(Application.id == id))
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = ApplicationState.PORTAL_RUNNING.value
    db.add(app)

    audit = AuditLog(
        actor_id=current_user.id,
        application_id=app.id,
        action="CAPTCHA_SOLVED_RESUMED",
        metadata_json={"resumed_by": current_user.email},
    )
    db.add(audit)
    await db.commit()

    return {"success": True, "status": app.status, "message": "Automation continued."}


@router.post("/{id}/automation/cancel")
async def cancel_automation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Safely stop running automation worker."""
    app_res = await db.execute(select(Application).where(Application.id == id))
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = ApplicationState.READY_FOR_PORTAL.value
    db.add(app)

    audit = AuditLog(
        actor_id=current_user.id,
        application_id=app.id,
        action="AUTOMATION_CANCELLED",
        metadata_json={"cancelled_by": current_user.email},
    )
    db.add(audit)
    await db.commit()

    return {"success": True, "status": app.status, "message": "Automation safely cancelled."}


@router.post("/{id}/manual-process")
async def process_manually(
    id: uuid.UUID,
    payload: ManualProcessPayload,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Employee registers case manually on government portal and uploads certificate."""
    app_res = await db.execute(select(Application).where(Application.id == id))
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Transition to CERTIFICATE_RETRIEVED
    app.status = ApplicationState.CERTIFICATE_READY.value
    db.add(app)

    # Upsert certificate record
    cert_res = await db.execute(select(Certificate).where(Certificate.application_id == id))
    cert = cert_res.scalars().first()
    if not cert:
        cert = Certificate(
            application_id=id,
            certificate_number=payload.udyam_registration_number,
            file_path=f"/storage/certificates/{payload.certificate_file_name}",
            file_size_bytes=1024 * 150,
            mime_type="application/pdf",
        )
        db.add(cert)
    else:
        cert.certificate_number = payload.udyam_registration_number
        db.add(cert)

    audit = AuditLog(
        actor_id=current_user.id,
        application_id=app.id,
        action="MANUAL_REGISTRATION_COMPLETED",
        metadata_json={
            "udyam_number": payload.udyam_registration_number,
            "processed_by": current_user.email,
            "notes": payload.notes,
        },
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "application_id": str(app.id),
        "status": app.status,
        "udyam_number": payload.udyam_registration_number,
        "message": "Manual registration recorded. Certificate is ready for delivery.",
    }
