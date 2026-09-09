"""Phase 14 — Client directory API.

Replaces the frontend hardcoded MOCK_CLIENTS array with real
data from the ``clients`` table. Branch-scoped like every other
read endpoint: SUPER_ADMIN may pass ``?branch_id=`` or see all,
everyone else is forced to their own branch.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.security import get_current_user, require_roles
from app.models.domain import Application, Client, User
from app.models.state import ApplicationState
from app.schemas.client import ClientWithStatsResponse

router = APIRouter(prefix="/clients", tags=["Clients"])


_TERMINAL_STATES = {
    ApplicationState.COMPLETED.value,
    ApplicationState.CERTIFICATE_READY.value,
    ApplicationState.SUBMITTED.value,
    ApplicationState.REGISTERED.value,
    ApplicationState.APPROVED.value,
}


@router.get("", response_model=List[ClientWithStatsResponse])
async def list_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    branch_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    )),
):
    """List clients with roll-up application stats.

    Branch scope: SUPER_ADMIN may pass ``?branch_id=`` or omit it for
    all branches; every other role is forced to their own branch.
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

    stmt = select(Client)
    if effective_branch_id is not None:
        stmt = stmt.where(Client.branch_id == effective_branch_id)
    stmt = stmt.order_by(Client.created_at.desc()).offset(skip).limit(limit)
    clients = (await db.execute(stmt)).scalars().all()

    if not clients:
        return []

    # One round-trip: per-client COUNT(*) + COUNT(*) WHERE status NOT IN
    # terminal states — covers both stats with a single GROUP BY.
    client_ids = [c.id for c in clients]
    counts_stmt = (
        select(
            Application.client_id,
            func.count(Application.id).label("total"),
            func.sum(
                func.case(
                    (
                        Application.status.notin_(_TERMINAL_STATES),
                        1,
                    ),
                    else_=0,
                )
            ).label("active"),
        )
        .where(Application.client_id.in_(client_ids))
        .group_by(Application.client_id)
    )
    rows = (await db.execute(counts_stmt)).all()
    stats = {row.client_id: (row.total or 0, row.active or 0) for row in rows}

    out: List[ClientWithStatsResponse] = []
    for c in clients:
        total, active = stats.get(c.id, (0, 0))
        out.append(
            ClientWithStatsResponse(
                id=c.id,
                business_name=c.business_name,
                applicant_name=c.applicant_name,
                mobile_number=c.mobile_number,
                email=c.email,
                pan_number=c.pan_number,
                gender=c.gender,
                social_category=c.social_category,
                divyang_status=c.divyang_status,
                branch_id=c.branch_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
                application_count=int(total),
                active_count=int(active),
            )
        )
    return out


@router.get("/{id}", response_model=ClientWithStatsResponse)
async def get_client(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    )),
):
    """Fetch one client with application counts.

    Branch scope: enforced manually because ``Client`` doesn't ride
    through ``assert_branch_scope``'s application-shaped signature.
    """
    result = await db.execute(select(Client).where(Client.id == id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if current_user.role != "SUPER_ADMIN":
        if current_user.branch_id is None or client.branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Cross-branch access denied",
            )

    counts_stmt = (
        select(
            func.count(Application.id).label("total"),
            func.sum(
                func.case(
                    (
                        Application.status.notin_(_TERMINAL_STATES),
                        1,
                    ),
                    else_=0,
                )
            ).label("active"),
        )
        .where(Application.client_id == id)
    )
    row = (await db.execute(counts_stmt)).one()
    return ClientWithStatsResponse(
        id=client.id,
        business_name=client.business_name,
        applicant_name=client.applicant_name,
        mobile_number=client.mobile_number,
        email=client.email,
        pan_number=client.pan_number,
        gender=client.gender,
        social_category=client.social_category,
        divyang_status=client.divyang_status,
        branch_id=client.branch_id,
        created_at=client.created_at,
        updated_at=client.updated_at,
        application_count=int(row.total or 0),
        active_count=int(row.active or 0),
    )
