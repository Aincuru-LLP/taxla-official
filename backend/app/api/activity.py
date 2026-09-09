"""Application Activity and Audit Feed API for TAXLA Operations Platform.

Combines immutable AuditLogs and WorkflowEvents into an ordered timeline.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db
from app.core.security import get_current_user
from app.models.domain import Application, AuditLog, WorkflowEvent, User

router = APIRouter(prefix="/applications", tags=["Activity"])


class ActivityEventItem(BaseModel):
    id: str
    action: str
    title: str
    description: Optional[str] = None
    actor_name: str
    actor_role: Optional[str] = None
    timestamp: str
    category: str  # "AUDIT" | "AUTOMATION" | "COMMUNICATION" | "PAYMENT"
    metadata: Dict[str, Any] = {}


@router.get("/{id}/activity", response_model=List[ActivityEventItem])
async def get_application_activity(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve unified chronological activity history for an application."""
    app_res = await db.execute(select(Application).where(Application.id == id))
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Fetch audit logs
    audit_stmt = (
        select(AuditLog)
        .where(AuditLog.application_id == id)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
    )
    audits = (await db.execute(audit_stmt)).scalars().all()

    # Fetch workflow events
    events_stmt = (
        select(WorkflowEvent)
        .where(WorkflowEvent.application_id == id)
        .order_by(WorkflowEvent.created_at.desc())
    )
    events = (await db.execute(events_stmt)).scalars().all()

    feed: List[ActivityEventItem] = []

    # Process audits
    for a in audits:
        meta = a.metadata_json or {}
        action_name = a.action
        cat = "AUDIT"
        if "PAYMENT" in action_name:
            cat = "PAYMENT"
        elif "WHATSAPP" in action_name or "REQUEST_INFO" in action_name or "SENT" in action_name:
            cat = "COMMUNICATION"
        elif "AUTOMATION" in action_name or "PORTAL" in action_name:
            cat = "AUTOMATION"

        feed.append(
            ActivityEventItem(
                id=f"audit-{a.id}",
                action=action_name,
                title=action_name.replace("_", " ").title(),
                description=meta.get("message") or meta.get("reason") or meta.get("notes"),
                actor_name=a.actor.name if a.actor else "System",
                actor_role=a.actor.role if a.actor else "SYSTEM",
                timestamp=a.created_at.isoformat() if a.created_at else "",
                category=cat,
                metadata=meta,
            )
        )

    # Process workflow events
    for e in events:
        feed.append(
            ActivityEventItem(
                id=f"evt-{e.id}",
                action=e.event_type,
                title=e.event_type.replace("_", " ").title(),
                description=f"State transitioned from {e.from_state} to {e.to_state}",
                actor_name="Workflow Engine",
                actor_role="SYSTEM",
                timestamp=e.created_at.isoformat() if e.created_at else "",
                category="AUTOMATION",
                metadata=e.payload_json or {},
            )
        )

    # Sort descending by timestamp
    feed.sort(key=lambda x: x.timestamp, reverse=True)
    return feed
