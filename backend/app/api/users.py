"""Phase 14 — User directory API.

Replaces the frontend hardcoded MOCK_USERS array. Operator+Reviewer
may read users in their own branch (so the directory is a "who can I
assign this to" reference); only BRANCH_ADMIN+ can mutate users
(invite/deactivate — Phase 14 deliberately ships read-only because the
invite flow needs email infra to be useful).
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.security import get_current_user, require_roles
from app.models.domain import AuditLog, User
from app.schemas.user_admin import UserListResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserListResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    role: Optional[str] = Query(None),
    branch_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    )),
):
    """List users in the caller's branch (or all branches for SUPER_ADMIN).

    ``last_active`` is computed from the audit log — the most recent
    audit_log row where this user is the actor. We do this once via a
    correlated subquery so we don't trigger N+1.
    """
    if current_user.role == "SUPER_ADMIN":
        effective_branch_id = branch_id
    else:
        if branch_id is not None and branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Cross-branch listing denied: branch_id must match caller's branch",
            )
        effective_branch_id = current_user.branch_id

    # Subquery: per-user max audit_log.created_at.
    last_active_sq = (
        select(
            AuditLog.actor_id,
            func.max(AuditLog.created_at).label("last_active"),
        )
        .where(AuditLog.actor_id.is_not(None))
        .group_by(AuditLog.actor_id)
        .subquery()
    )

    stmt = (
        select(User, last_active_sq.c.last_active)
        .outerjoin(last_active_sq, last_active_sq.c.actor_id == User.id)
    )
    if effective_branch_id is not None:
        stmt = stmt.where(User.branch_id == effective_branch_id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)

    rows = (await db.execute(stmt)).all()

    return [
        UserListResponse(
            id=u.id,
            name=u.name,
            email=u.email,
            role=u.role,
            branch_id=u.branch_id,
            status=u.status,
            created_at=u.created_at,
            updated_at=u.updated_at,
            last_active=last_active,
        )
        for u, last_active in rows
    ]


@router.get("/{id}", response_model=UserListResponse)
async def get_user(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    )),
):
    """Fetch one user with last_active.

    Branch scope: any caller can read users in their own branch (so
    they can pick a reviewer to assign); cross-branch reads 403.
    """
    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.role != "SUPER_ADMIN":
        if current_user.branch_id is None or user.branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Cross-branch access denied",
            )

    last_active_row = (
        await db.execute(
            select(func.max(AuditLog.created_at))
            .where(AuditLog.actor_id == user.id)
        )
    ).scalar_one_or_none()

    return UserListResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        branch_id=user.branch_id,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_active=last_active_row,
    )
