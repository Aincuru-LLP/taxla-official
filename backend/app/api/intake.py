"""API Router for AI Conversational Intake & Requirement Management."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db as get_db
from app.core.security import get_current_user, require_roles
from app.models.domain import Application, ApplicationRequirement, User
from app.services.intake_service import IntakeService
from app.services.requirement_engine import RequirementEngine

router = APIRouter(tags=["AI Intake & Requirements"])


class IntakeAnswerRequest(BaseModel):
    field_key: str
    answer: str


class RequirementItemResponse(BaseModel):
    id: uuid.UUID
    requirement_key: str
    display_label: str
    category: str
    is_required: bool
    is_completed: bool
    source: Optional[str] = None
    value: Optional[str] = None
    validation_status: str
    validation_error: Optional[str] = None
    sort_order: int


@router.post(
    "/applications/{application_id}/requirements/recalculate",
    dependencies=[Depends(require_roles("SUPER_ADMIN", "BRANCH_ADMIN", "OPERATOR"))],
)
async def recalculate_requirements(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger on-demand recalculation of requirements and completion score."""
    pct = await RequirementEngine.recalculate_completion(application_id, db)
    return {"application_id": application_id, "completion_percentage": pct}


@router.get(
    "/applications/{application_id}/intake/next-question",
    dependencies=[Depends(require_roles("SUPER_ADMIN", "BRANCH_ADMIN", "OPERATOR"))],
)
async def get_next_intake_question(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the next unfulfilled requirement formatted as a conversational question."""
    q_data = await IntakeService.get_next_question(application_id, db)
    if not q_data:
        pct = await RequirementEngine.recalculate_completion(application_id, db)
        return {
            "all_completed": True,
            "completion_percentage": pct,
            "message": "All mandatory requirements have been fulfilled!",
        }

    return {
        "all_completed": False,
        **q_data,
    }


@router.post(
    "/applications/{application_id}/intake/answer",
    dependencies=[Depends(require_roles("SUPER_ADMIN", "BRANCH_ADMIN", "OPERATOR"))],
)
async def submit_intake_answer(
    application_id: uuid.UUID,
    payload: IntakeAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit answer to conversational intake, validate format, and update state."""
    result = await IntakeService.process_answer(
        application_id=application_id,
        field_key=payload.field_key,
        answer=payload.answer,
        db=db,
        actor_id=current_user.id,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Validation failed for provided answer."),
        )

    return result
