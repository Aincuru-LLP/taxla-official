"""Dashboard API for TAXLA Operations Platform.

Provides live SQL aggregate counts and operational 'Needs Attention' application lists.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db
from app.core.security import get_current_user
from app.models.domain import Application, User, Client
from app.models.state import ApplicationState

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class DashboardSummaryResponse(BaseModel):
    total_applications: int
    pending_requirements: int
    pending_payment: int
    ready_for_automation: int
    automation_running: int
    waiting_for_otp: int
    completed: int


class NeedsAttentionItem(BaseModel):
    id: uuid.UUID
    application_number: str
    customer_name: str
    customer_phone: Optional[str] = None
    status: str
    processing_mode: str
    assigned_employee_name: Optional[str] = None
    created_at: str
    updated_at: str
    action_required: str


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate operational KPIs from real PostgreSQL records."""
    # Count totals per status
    status_counts_stmt = select(Application.status, func.count(Application.id)).group_by(Application.status)
    rows = (await db.execute(status_counts_stmt)).all()
    counts: Dict[str, int] = {row[0].upper(): int(row[1]) for row in rows}

    total = sum(counts.values())

    # Pending Requirements: NEW, FORM_SENT
    pending_requirements = counts.get("NEW", 0) + counts.get("FORM_SENT", 0)

    # Pending Payment: FORM_SUBMITTED, REVIEW_REQUIRED, READY_FOR_PAYMENT, DOCUMENTS_UPLOADED, VALIDATION_REVIEW, HUMAN_REVIEW_REQUIRED, NIC_REVIEW, HUMAN_REVIEW
    pending_payment = (
        counts.get("FORM_SUBMITTED", 0)
        + counts.get("REVIEW_REQUIRED", 0)
        + counts.get("READY_FOR_PAYMENT", 0)
        + counts.get("DOCUMENTS_UPLOADED", 0)
        + counts.get("VALIDATION_REVIEW", 0)
        + counts.get("HUMAN_REVIEW_REQUIRED", 0)
        + counts.get("NIC_REVIEW", 0)
        + counts.get("HUMAN_REVIEW", 0)
    )

    # Ready for Automation: PAYMENT_COMPLETED, READY_FOR_AUTOMATION, READY_FOR_PORTAL, APPROVED
    ready_for_automation = (
        counts.get("PAYMENT_COMPLETED", 0)
        + counts.get("READY_FOR_AUTOMATION", 0)
        + counts.get("READY_FOR_PORTAL", 0)
        + counts.get("APPROVED", 0)
    )

    # Automation Running: AUTOMATION_RUNNING, PORTAL_RUNNING, SUBMITTING, SUBMITTED
    automation_running = (
        counts.get("AUTOMATION_RUNNING", 0)
        + counts.get("PORTAL_RUNNING", 0)
        + counts.get("SUBMITTING", 0)
        + counts.get("SUBMITTED", 0)
    )

    # Waiting for OTP: OTP_REQUIRED, AADHAAR_OTP
    waiting_for_otp = counts.get("OTP_REQUIRED", 0) + counts.get("AADHAAR_OTP", 0)

    # Completed: COMPLETED, CERTIFICATE_READY, CERTIFICATE_RETRIEVED, REGISTERED, CLIENT_NOTIFIED
    completed = (
        counts.get("COMPLETED", 0)
        + counts.get("CERTIFICATE_READY", 0)
        + counts.get("CERTIFICATE_RETRIEVED", 0)
        + counts.get("REGISTERED", 0)
        + counts.get("CLIENT_NOTIFIED", 0)
    )

    return DashboardSummaryResponse(
        total_applications=total,
        pending_requirements=pending_requirements,
        pending_payment=pending_payment,
        ready_for_automation=ready_for_automation,
        automation_running=automation_running,
        waiting_for_otp=waiting_for_otp,
        completed=completed,
    )


@router.get("/needs-attention", response_model=List[NeedsAttentionItem])
async def get_needs_attention(
    limit: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch prioritized applications requiring operator intervention."""
    attention_statuses = [
        "OTP_REQUIRED",
        "AADHAAR_OTP",
        "READY_FOR_AUTOMATION",
        "READY_FOR_PORTAL",
        "READY_FOR_PAYMENT",
        "REVIEW_REQUIRED",
        "NIC_REVIEW",
        "HUMAN_REVIEW",
        "VALIDATION_REVIEW",
        "FORM_SUBMITTED",
        "MANUAL_PROCESSING",
        "AUTOMATION_FAILED",
        "EXCEPTION",
    ]

    stmt = (
        select(Application)
        .where(Application.status.in_(attention_statuses))
        .options(
            selectinload(Application.client),
            selectinload(Application.assigned_user),
        )
        .order_by(Application.updated_at.desc())
        .limit(limit)
    )

    apps = (await db.execute(stmt)).scalars().all()

    items = []
    for app in apps:
        s = app.status.upper()
        if "OTP" in s:
            action = "Enter OTP to resume automation"
        elif s in ("READY_FOR_AUTOMATION", "READY_FOR_PORTAL", "APPROVED"):
            action = "Start Automation or Manual Processing"
        elif s == "READY_FOR_PAYMENT":
            action = "Confirm payment receipt"
        elif s in ("REVIEW_REQUIRED", "NIC_REVIEW", "VALIDATION_REVIEW", "HUMAN_REVIEW"):
            action = "Review submitted requirements"
        elif s == "FORM_SUBMITTED":
            action = "Review customer submission"
        elif s == "MANUAL_PROCESSING":
            action = "Complete manual registration and upload certificate"
        elif "FAIL" in s or s == "EXCEPTION":
            action = "Inspect failure and retry"
        else:
            action = "Review application"

        cust_name = app.client.business_name if app.client else "Client"
        if app.client and app.client.applicant_name:
            cust_name = f"{app.client.business_name} ({app.client.applicant_name})"

        items.append(
            NeedsAttentionItem(
                id=app.id,
                application_number=app.application_number,
                customer_name=cust_name,
                customer_phone=app.client.mobile_number if app.client else None,
                status=app.status,
                processing_mode="MANUAL" if app.status == "MANUAL_PROCESSING" else "AUTOMATION",
                assigned_employee_name=app.assigned_user.name if app.assigned_user else "Unassigned",
                created_at=app.created_at.isoformat() if app.created_at else "",
                updated_at=app.updated_at.isoformat() if app.updated_at else "",
                action_required=action,
            )
        )

    return items
