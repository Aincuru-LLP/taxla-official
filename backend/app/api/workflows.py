"""Phase 14 — Workflows summary API.

Replaces the frontend hardcoded ``0`` counts in
``workflows/page.tsx``. Collapses the 24-state machine into the
5 operator-visible pipeline stages from the Kanban dashboard.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.security import get_current_user, require_roles
from app.models.domain import Application, User
from app.schemas.workflows import WorkflowStageCount, WorkflowsSummaryResponse

router = APIRouter(prefix="/workflows", tags=["Workflows"])


# Stage buckets — must mirror the buckets in
# ``frontend/src/components/KanbanDashboard.tsx`` so the two views agree.
_STAGES = [
    {
        "key": "intake",
        "label": "Intake",
        "description": "Newly created applications",
        "states": ("NEW", "DOCUMENTS_UPLOADED"),
    },
    {
        "key": "processing",
        "label": "Processing",
        "description": "OCR + extraction in flight",
        "states": (
            "PROCESSING",
            "EXTRACTED",
            "VALIDATION",
            "PORTAL_RUNNING",
            "SUBMITTING",
        ),
    },
    {
        "key": "review",
        "label": "Review",
        "description": "Awaiting reviewer action",
        "states": (
            "NIC_REVIEW",
            "READY_FOR_PORTAL",
            "HUMAN_REVIEW",
            "VALIDATION_REVIEW",
        ),
    },
    {
        "key": "portal",
        "label": "Portal",
        "description": "Udyam portal automation",
        "states": (
            "OTP_REQUIRED",
            "OTP_VERIFIED",
            "PAN_VERIFICATION",
            "DATA_VERIFICATION",
            "AADHAAR_OTP",
        ),
    },
    {
        "key": "completed",
        "label": "Completed",
        "description": "Certificate issued",
        "states": (
            "APPROVED",
            "SUBMITTED",
            "CERTIFICATE_READY",
            "COMPLETED",
            "REGISTERED",
        ),
    },
]


@router.get("/summary", response_model=WorkflowsSummaryResponse)
async def workflows_summary(
    branch_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    )),
):
    """Per-pipeline-stage application counts.

    Branch scope: SUPER_ADMIN may pass ``?branch_id=`` or omit for all
    branches; everyone else is forced to their own branch.
    """
    if current_user.role == "SUPER_ADMIN":
        effective_branch_id = branch_id
    else:
        effective_branch_id = current_user.branch_id

    base = select(Application.status)
    if effective_branch_id is not None:
        base = base.where(Application.branch_id == effective_branch_id)
    rows = (await db.execute(base)).scalars().all()
    status_counts: dict[str, int] = {}
    for s in rows:
        status_counts[s] = status_counts.get(s, 0) + 1

    stages: list[WorkflowStageCount] = []
    for stage in _STAGES:
        count = sum(status_counts.get(s, 0) for s in stage["states"])
        stages.append(
            WorkflowStageCount(
                key=stage["key"],
                label=stage["label"],
                description=stage["description"],
                count=count,
            )
        )

    # In-flight = anything that isn't terminal-success (matches Kanban logic).
    terminal = {
        "COMPLETED",
        "CERTIFICATE_READY",
        "SUBMITTED",
        "REGISTERED",
        "APPROVED",
    }
    total_in_flight = sum(
        c for s, c in status_counts.items() if s not in terminal
    )

    return WorkflowsSummaryResponse(
        stages=stages,
        total_in_flight=total_in_flight,
    )