import uuid
import json
import redis.asyncio as aioredis
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_db
from app.core.config import settings
from app.core.security import get_current_user, require_roles, assert_branch_scope
from app.models.domain import User, Branch, Workflow, AuditLog, Application, WorkflowEvent
from app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    AuditLogResponse,
    WorkflowEventResponse,
)
from app.repositories.application import ApplicationRepository

router = APIRouter(prefix="/applications", tags=["Applications"])

async def notify_clients(event_type: str, data: dict):
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL)
        message = json.dumps({"event": event_type, "data": data})
        await redis_client.publish("taxla:updates", message)
        await redis_client.close()
    except Exception as e:
        pass


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN"))
):
    """Create a new Udyam application.

    Allowed roles: OPERATOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: OPERATOR/BRANCH_ADMIN must create applications in their own
    branch (payload.branch_id == current_user.branch_id). SUPER_ADMIN may
    target any branch.
    """
    if not payload.branch_id:
        if current_user.branch_id:
            payload.branch_id = current_user.branch_id
        else:
            first_branch = (await db.execute(select(Branch))).scalars().first()
            if first_branch:
                payload.branch_id = first_branch.id

    if current_user.role != "SUPER_ADMIN" and payload.branch_id != current_user.branch_id:
        raise HTTPException(
            status_code=403,
            detail="Cross-branch creation denied: branch_id must match caller's branch",
        )

    # Check branch exists
    if payload.branch_id:
        branch_res = await db.execute(select(Branch).where(Branch.id == payload.branch_id))
        branch = branch_res.scalar_one_or_none()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")

    repo = ApplicationRepository(db)

    try:
        application = await repo.create_application(payload, user_id=current_user.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Initialize Workflow state
    workflow = Workflow(
        application_id=application.id,
        definition_version="1.0",
        current_node="NEW",
        status="RUNNING",
        context_json={"created_by": str(current_user.id)}
    )
    db.add(workflow)

    # Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        application_id=application.id,
        action="APPLICATION_CREATED",
        metadata_json={"business_name": payload.business_name, "applicant_name": payload.applicant_name}
    )
    db.add(audit)

    await db.commit()

    # Reload with full relations
    full_app = await repo.get_application(application.id)
    await notify_clients("APPLICATION_CREATED", {"id": str(full_app.id)})
    return full_app


@router.get("", response_model=List[ApplicationResponse])
async def list_applications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    branch_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """List applications.

    Allowed roles: OPERATOR, REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: SUPER_ADMIN may pass ?branch_id= and see all branches, or
    see everything unfiltered. Every other role is forced to its own branch.
    """
    repo = ApplicationRepository(db)
    if current_user.role == "SUPER_ADMIN":
        effective_branch_id = branch_id  # may be None -> all branches
    else:
        # Force branch_id to the caller's branch; reject attempts to read another.
        if branch_id is not None and branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Cross-branch listing denied: branch_id must match caller's branch",
            )
        effective_branch_id = current_user.branch_id
    apps = await repo.list_applications(
        skip=skip, limit=limit, branch_id=effective_branch_id,
    )
    return apps


@router.get("/{id}", response_model=ApplicationResponse)
async def get_application(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Fetch one application by id.

    Allowed roles: all roles with branch access (OPERATOR, REVIEWER_AUDITOR,
    BRANCH_ADMIN, SUPER_ADMIN). Branch scope enforced via ``assert_branch_scope``.
    """
    repo = ApplicationRepository(db)
    app = await repo.get_application(id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)
    return app


# ---------------------------------------------------------------------------
# Phase 11 — read-only timeline endpoints (audit log + workflow events)
# ---------------------------------------------------------------------------
@router.get("/{id}/audit", response_model=List[AuditLogResponse])
async def get_application_audit_log(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Return the immutable audit log for one application, newest first.

    Allowed roles: same as GET /applications/{id}. Branch scope is enforced
    via ``assert_branch_scope`` against the parent application — a 404 on
    the parent is propagated, and a cross-branch attempt returns 403.
    """
    repo = ApplicationRepository(db)
    app = await repo.get_application(id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.application_id == id)
        .order_by(AuditLog.created_at.desc())
    )
    rows = result.scalars().all()
    return rows


@router.get("/{id}/workflow-events", response_model=List[WorkflowEventResponse])
async def get_application_workflow_events(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Return workflow node-transition events for one application, newest first.

    Allowed roles: same as GET /applications/{id}. Branch scope enforced via
    ``assert_branch_scope`` against the parent application.
    """
    repo = ApplicationRepository(db)
    app = await repo.get_application(id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    result = await db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.application_id == id)
        .order_by(WorkflowEvent.created_at.desc())
    )
    rows = result.scalars().all()
    return rows


@router.patch("/{id}", response_model=ApplicationResponse)
async def update_application(
    id: uuid.UUID,
    payload: ApplicationUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN"))
):
    """Update an existing application.

    Allowed roles: OPERATOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    Only valid in NEW / DATA_VERIFICATION states per documents/04.
    """
    repo = ApplicationRepository(db)

    # Verify exists + branch scope BEFORE mutating.
    existing = await repo.get_application(id)
    if not existing:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, existing)

    # Restrict to states where editing makes sense.
    editable_states = {"NEW", "DATA_VERIFICATION"}
    if existing.status not in editable_states:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot edit application in state {existing.status}; "
                f"editable states: {sorted(editable_states)}"
            ),
        )

    updated = await repo.update_application(id, payload)

    # Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        application_id=updated.id,
        action="APPLICATION_UPDATED",
        metadata_json={"fields": list(payload.model_dump(exclude_unset=True).keys())}
    )
    db.add(audit)
    await db.commit()

    await notify_clients("APPLICATION_UPDATED", {"id": str(updated.id)})
    return updated
