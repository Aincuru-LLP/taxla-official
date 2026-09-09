"""Phase 08 — Trigger CRUD.

These endpoints are for ``BRANCH_ADMIN`` and above. Every write path
goes through ``assert_branch_scope`` so triggers cannot escape their
branch. Read access is open to anyone authenticated; the WHERE clause
filters by ``user.branch_id`` so cross-branch data never leaks.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import assert_branch_scope, get_current_user, require_roles
from app.core.database import get_async_db as get_db
from app.models.domain import Action, Trigger, User

logger = logging.getLogger("taxla.api.triggers")

router = APIRouter(prefix="/triggers", tags=["triggers"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_VALID_ACTION_TYPES = {"HTTP_WEBHOOK", "EMAIL", "SHELL", "STATE_TRANSITION", "PLAYWRIGHT"}


class ActionIn(BaseModel):
    """Config for an action in a trigger payload."""
    type: str
    config_json: Dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0
    is_active: bool = True

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in _VALID_ACTION_TYPES:
            raise ValueError(f"action type must be one of {sorted(_VALID_ACTION_TYPES)}")
        return v


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    type: str
    config_json: Dict[str, Any]
    sort_order: int
    is_active: bool


class TriggerIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    event_pattern: str = Field(min_length=1, max_length=255)
    condition_json: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    actions: List[ActionIn] = Field(default_factory=list)


class TriggerPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    event_pattern: Optional[str] = Field(default=None, min_length=1, max_length=255)
    condition_json: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    actions: Optional[List[ActionIn]] = None


class TriggerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    branch_id: UUID
    name: str
    event_pattern: str
    condition_json: Dict[str, Any]
    is_active: bool
    created_by: UUID
    last_run_json: Optional[Dict[str, Any]] = None
    created_at: Any
    updated_at: Any
    actions: List[ActionOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_trigger_or_404(
    db: AsyncSession, trigger_id: UUID
) -> Trigger:
    result = await db.execute(
        select(Trigger)
        .where(Trigger.id == trigger_id)
        .options(selectinload(Trigger.actions))
    )
    trigger = result.scalars().first()
    if not trigger:
        raise HTTPException(status_code=404, detail="trigger not found")
    return trigger


def _validate_event_pattern(pattern: str) -> None:
    """Tiny sanity check — pattern must be ASCII and not contain weird
    stuff like newlines. The dispatcher uses fnmatch anyway, so this is
    just to keep the DB clean.
    """
    if "\n" in pattern or "\r" in pattern:
        raise HTTPException(
            status_code=422,
            detail="event_pattern must not contain newline characters",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[TriggerOut])
async def list_triggers(
    event_pattern: Optional[str] = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List triggers for the current user's branch."""
    stmt = (
        select(Trigger)
        .where(Trigger.branch_id == current_user.branch_id)
        .options(selectinload(Trigger.actions))
        .order_by(Trigger.created_at.desc())
    )
    if not include_inactive:
        stmt = stmt.where(Trigger.is_active.is_(True))
    if event_pattern:
        stmt = stmt.where(Trigger.event_pattern == event_pattern)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "",
    response_model=TriggerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_trigger(
    body: TriggerIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("BRANCH_ADMIN", "SUPER_ADMIN")),
):
    """Create a trigger and its actions.

    The new trigger is scoped to ``current_user.branch_id``.
    """
    _validate_event_pattern(body.event_pattern)
    trigger = Trigger(
        branch_id=current_user.branch_id,
        name=body.name,
        event_pattern=body.event_pattern,
        condition_json=body.condition_json,
        is_active=body.is_active,
        created_by=current_user.id,
    )
    for a in body.actions:
        trigger.actions.append(
            Action(
                type=a.type,
                config_json=a.config_json,
                sort_order=a.sort_order,
                is_active=a.is_active,
            )
        )
    db.add(trigger)
    await db.commit()
    # Re-fetch with eager-loaded actions so the response shape is right.
    return await _load_trigger_or_404(db, trigger.id)


@router.get("/{trigger_id}", response_model=TriggerOut)
async def get_trigger(
    trigger_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trigger = await _load_trigger_or_404(db, trigger_id)
    assert_branch_scope(current_user, trigger)
    return trigger


@router.patch("/{trigger_id}", response_model=TriggerOut)
async def patch_trigger(
    trigger_id: UUID,
    body: TriggerPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("BRANCH_ADMIN", "SUPER_ADMIN")),
):
    trigger = await _load_trigger_or_404(db, trigger_id)
    assert_branch_scope(current_user, trigger)

    if body.name is not None:
        trigger.name = body.name
    if body.event_pattern is not None:
        _validate_event_pattern(body.event_pattern)
        trigger.event_pattern = body.event_pattern
    if body.condition_json is not None:
        trigger.condition_json = body.condition_json
    if body.is_active is not None:
        trigger.is_active = body.is_active

    if body.actions is not None:
        # Replace-all semantics — simpler than diffing for a Phase 08 MVP.
        await db.execute(
            delete(Action).where(Action.trigger_id == trigger.id)
        )
        await db.flush()
        for a in body.actions:
            db.add(
                Action(
                    trigger_id=trigger.id,
                    type=a.type,
                    config_json=a.config_json,
                    sort_order=a.sort_order,
                    is_active=a.is_active,
                )
            )
    await db.commit()
    return await _load_trigger_or_404(db, trigger.id)


@router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    trigger_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("BRANCH_ADMIN", "SUPER_ADMIN")),
):
    trigger = await _load_trigger_or_404(db, trigger_id)
    assert_branch_scope(current_user, trigger)
    # actions are FK ON DELETE CASCADE — single delete does the right thing.
    await db.delete(trigger)
    await db.commit()
    return None