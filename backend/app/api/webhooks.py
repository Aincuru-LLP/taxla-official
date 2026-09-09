"""Phase 12 — Webhook CRUD API.

Endpoints (all under ``/api/v1/webhooks``):

  * ``GET    /``              — list webhooks in caller's branch.
  * ``POST   /``              — create a webhook. The HMAC ``secret`` is
                                minted server-side and returned **once**
                                in the response body; subsequent reads
                                never include it. Mirrors Stripe's
                                webhook UX.
  * ``GET    /{id}``          — read metadata (no secret).
  * ``PATCH  /{id}``          — toggle ``is_active``, change name/url/
                                subscribed_events. Cannot rotate the
                                secret — that's a separate ``POST /rotate``.
  * ``DELETE /{id}``          — delete the subscription and cascade the
                                delivery log.
  * ``GET    /{id}/deliveries`` — paginated delivery attempts (most
                                recent first).
  * ``POST   /{id}/test``     — fire a synthetic ``webhook.ping`` event
                                end-to-end so the operator can confirm
                                their receiver works without waiting for
                                a real state transition.

RBAC: writes require ``BRANCH_ADMIN`` or ``SUPER_ADMIN``. Reads are
open to any authenticated user in the branch — operators viewing
debug data shouldn't need admin rights.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db as get_db
from app.core.security import (
    assert_branch_scope,
    get_current_user,
    require_roles,
)
from app.models.domain import User, Webhook, WebhookDelivery

logger = logging.getLogger("taxla.api.webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


def _normalize_events(value: List[str]) -> List[str]:
    """Strip, dedupe, drop empties. Order preserved so a UI round-trip
    doesn't shuffle the list."""
    seen: List[str] = []
    for raw in value:
        if not isinstance(raw, str):
            continue
        s = raw.strip()
        if s and s not in seen:
            seen.append(s)
    return seen


class WebhookIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: HttpUrl
    subscribed_events: List[str] = Field(default_factory=list)
    is_active: bool = True

    @field_validator("subscribed_events")
    @classmethod
    def _clean_events(cls, v: List[str]) -> List[str]:
        return _normalize_events(v)


class WebhookPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    url: Optional[HttpUrl] = None
    subscribed_events: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator("subscribed_events")
    @classmethod
    def _clean_events(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        return _normalize_events(v)


class WebhookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    branch_id: UUID
    name: str
    url: str
    subscribed_events: List[str]
    is_active: bool
    last_triggered_at: Optional[Any] = None
    last_status: Optional[int] = None
    last_error: Optional[str] = None
    created_at: Any
    updated_at: Any


class WebhookCreated(WebhookOut):
    """Returned only on POST. Carries the freshly-minted HMAC secret.

    The same payload could have been sent via an out-of-band channel,
    but the "show once, then never again" UX is what every webhook
    provider ships and what operators expect.
    """
    secret: str


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    webhook_id: UUID
    event_id: Optional[UUID] = None
    event_name: Optional[str] = None
    attempt_number: int
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    attempted_at: Any
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mint_secret() -> str:
    """64-char URL-safe hex. Plenty of entropy for HMAC-SHA256."""
    return secrets.token_hex(32)


async def _load_or_404(
    db: AsyncSession, webhook_id: UUID
) -> Webhook:
    row = (await db.execute(
        select(Webhook).where(Webhook.id == webhook_id)
    )).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="webhook not found")
    return row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[WebhookOut])
async def list_webhooks(
    include_inactive: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List webhooks for the current user's branch."""
    stmt = (
        select(Webhook)
        .where(Webhook.branch_id == current_user.branch_id)
        .order_by(Webhook.created_at.desc())
    )
    if not include_inactive:
        stmt = stmt.where(Webhook.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.post(
    "",
    response_model=WebhookCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    body: WebhookIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("BRANCH_ADMIN", "SUPER_ADMIN")),
):
    """Create a webhook and return its HMAC secret exactly once."""
    if current_user.branch_id is None:
        raise HTTPException(
            status_code=400, detail="user has no branch assignment"
        )
    webhook = Webhook(
        branch_id=current_user.branch_id,
        name=body.name,
        url=str(body.url),
        secret=_mint_secret(),
        subscribed_events=body.subscribed_events,
        is_active=body.is_active,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.get("/{webhook_id}", response_model=WebhookOut)
async def get_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    webhook = await _load_or_404(db, webhook_id)
    await assert_branch_scope(current_user, webhook)
    return webhook


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def patch_webhook(
    webhook_id: UUID,
    body: WebhookPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("BRANCH_ADMIN", "SUPER_ADMIN")),
):
    webhook = await _load_or_404(db, webhook_id)
    await assert_branch_scope(current_user, webhook)

    if body.name is not None:
        webhook.name = body.name
    if body.url is not None:
        webhook.url = str(body.url)
    if body.subscribed_events is not None:
        webhook.subscribed_events = body.subscribed_events
    if body.is_active is not None:
        webhook.is_active = body.is_active
    webhook.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(webhook)
    return webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("BRANCH_ADMIN", "SUPER_ADMIN")),
):
    webhook = await _load_or_404(db, webhook_id)
    await assert_branch_scope(current_user, webhook)
    # deliveries cascade via FK ON DELETE CASCADE.
    await db.delete(webhook)
    await db.commit()
    return None


@router.get(
    "/{webhook_id}/deliveries",
    response_model=List[DeliveryOut],
)
async def list_deliveries(
    webhook_id: UUID,
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    webhook = await _load_or_404(db, webhook_id)
    await assert_branch_scope(current_user, webhook)
    stmt = (
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook.id)
        .order_by(WebhookDelivery.attempted_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.post(
    "/{webhook_id}/test",
    status_code=status.HTTP_202_ACCEPTED,
)
async def test_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("BRANCH_ADMIN", "SUPER_ADMIN")),
):
    """Fire a synthetic ``webhook.ping`` so the operator can confirm
    the receiver works without waiting for a real state transition.

    Returns ``{delivered: bool, status_code, error}`` from the first
    attempt — no retry loop, since this is a manual smoke test.
    """
    webhook = await _load_or_404(db, webhook_id)
    await assert_branch_scope(current_user, webhook)

    from app.services.webhook_delivery import deliver_once

    event = {
        "event": "webhook.ping",
        "event_id": str(uuid.uuid4()),
        "branch_id": str(webhook.branch_id),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"triggered_by": str(current_user.id)},
    }
    try:
        delivery = await deliver_once(webhook, event, 1, db)
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=502, detail=f"webhook delivery failed: {exc!r}"
        )
    await db.commit()
    return {
        "delivered": delivery.status_code is not None and 200 <= delivery.status_code < 300,
        "status_code": delivery.status_code,
        "error": delivery.error,
    }