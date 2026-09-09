"""Customers Directory and Profile API for TAXLA Operations Platform.

Enforces clear separation: Customers are distinct entities that own multiple Applications.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db
from app.core.security import get_current_user
from app.models.domain import Application, Client, User

router = APIRouter(prefix="/customers", tags=["Customers"])


class CustomerCreateRequest(BaseModel):
    business_name: str = Field(min_length=2)
    applicant_name: str = Field(min_length=2)
    mobile_number: str = Field(min_length=10, max_length=15)
    email: Optional[str] = None
    pan_number: Optional[str] = None
    social_category: Optional[str] = "General"
    gender: Optional[str] = "Male"


class CustomerUpdateRequest(BaseModel):
    business_name: Optional[str] = None
    applicant_name: Optional[str] = None
    mobile_number: Optional[str] = None
    email: Optional[str] = None
    pan_number: Optional[str] = None
    social_category: Optional[str] = None
    gender: Optional[str] = None


class CustomerListItem(BaseModel):
    id: uuid.UUID
    business_name: str
    applicant_name: str
    mobile_number: str
    email: Optional[str] = None
    applications_count: int
    active_applications_count: int
    created_at: str
    updated_at: str


class CustomerApplicationItem(BaseModel):
    id: uuid.UUID
    application_number: str
    service: str
    status: str
    processing_mode: str
    created_at: str
    updated_at: str


class CustomerDetailResponse(BaseModel):
    id: uuid.UUID
    business_name: str
    applicant_name: str
    mobile_number: str
    email: Optional[str] = None
    pan_number: Optional[str] = None
    social_category: Optional[str] = None
    gender: Optional[str] = None
    whatsapp_status: str
    created_at: str
    updated_at: str
    applications: List[CustomerApplicationItem]


@router.get("", response_model=Dict[str, Any])
async def list_customers(
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """List all customers with applications roll-up counts."""
    base_stmt = select(Client)
    if search:
        pattern = f"%{search.strip()}%"
        base_stmt = base_stmt.where(
            or_(
                Client.business_name.ilike(pattern),
                Client.applicant_name.ilike(pattern),
                Client.mobile_number.ilike(pattern),
                Client.pan_number.ilike(pattern),
                Client.email.ilike(pattern),
            )
        )

    # Total count
    count_stmt = select(func.count(Client.id)).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginated clients with applications loaded
    stmt = (
        base_stmt.options(selectinload(Client.applications))
        .order_by(Client.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    clients = (await db.execute(stmt)).scalars().all()

    items = []
    for c in clients:
        apps = c.applications or []
        active_apps = [a for a in apps if a.status not in ("COMPLETED", "CANCELLED", "EXCEPTION")]
        items.append(
            CustomerListItem(
                id=c.id,
                business_name=c.business_name,
                applicant_name=c.applicant_name,
                mobile_number=c.mobile_number,
                email=c.email,
                applications_count=len(apps),
                active_applications_count=len(active_apps),
                created_at=c.created_at.isoformat() if c.created_at else "",
                updated_at=c.updated_at.isoformat() if c.updated_at else "",
            )
        )

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("", response_model=CustomerDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new customer profile."""
    # Check duplicate phone
    existing = (
        await db.execute(select(Client).where(Client.mobile_number == payload.mobile_number))
    ).scalars().first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A customer with phone {payload.mobile_number} already exists ({existing.business_name}).",
        )

    client = Client(
        business_name=payload.business_name,
        applicant_name=payload.applicant_name,
        mobile_number=payload.mobile_number,
        email=payload.email,
        pan_number=payload.pan_number,
        social_category=payload.social_category,
        gender=payload.gender,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    return CustomerDetailResponse(
        id=client.id,
        business_name=client.business_name,
        applicant_name=client.applicant_name,
        mobile_number=client.mobile_number,
        email=client.email,
        pan_number=client.pan_number,
        social_category=client.social_category,
        gender=client.gender,
        whatsapp_status="CONNECTED",
        created_at=client.created_at.isoformat() if client.created_at else "",
        updated_at=client.updated_at.isoformat() if client.updated_at else "",
        applications=[],
    )


@router.get("/{id}", response_model=CustomerDetailResponse)
async def get_customer(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch customer profile and list of all linked applications."""
    stmt = (
        select(Client)
        .where(Client.id == id)
        .options(selectinload(Client.applications))
    )
    client = (await db.execute(stmt)).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Customer not found")

    app_items = []
    for a in client.applications or []:
        app_items.append(
            CustomerApplicationItem(
                id=a.id,
                application_number=a.application_number,
                service=a.workflow_type or "MSME_REGISTRATION",
                status=a.status,
                processing_mode="MANUAL" if a.status == "MANUAL_PROCESSING" else "AUTOMATION",
                created_at=a.created_at.isoformat() if a.created_at else "",
                updated_at=a.updated_at.isoformat() if a.updated_at else "",
            )
        )

    return CustomerDetailResponse(
        id=client.id,
        business_name=client.business_name,
        applicant_name=client.applicant_name,
        mobile_number=client.mobile_number,
        email=client.email,
        pan_number=client.pan_number,
        social_category=client.social_category,
        gender=client.gender,
        whatsapp_status="CONNECTED",
        created_at=client.created_at.isoformat() if client.created_at else "",
        updated_at=client.updated_at.isoformat() if client.updated_at else "",
        applications=app_items,
    )


@router.patch("/{id}", response_model=CustomerDetailResponse)
async def update_customer(
    id: uuid.UUID,
    payload: CustomerUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Update customer profile information."""
    stmt = select(Client).where(Client.id == id).options(selectinload(Client.applications))
    client = (await db.execute(stmt)).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Customer not found")

    if payload.business_name:
        client.business_name = payload.business_name
    if payload.applicant_name:
        client.applicant_name = payload.applicant_name
    if payload.mobile_number:
        client.mobile_number = payload.mobile_number
    if payload.email:
        client.email = payload.email
    if payload.pan_number:
        client.pan_number = payload.pan_number
    if payload.social_category:
        client.social_category = payload.social_category
    if payload.gender:
        client.gender = payload.gender

    db.add(client)
    await db.commit()
    await db.refresh(client)

    return await get_customer(id, db, current_user)
