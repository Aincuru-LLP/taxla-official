"""Phase 14 — Analytics / reports overview API.

Replaces the frontend hardcoded KPI numbers + chart heights in
``reports/page.tsx``. Everything is derived from the application
lifecycle — no new analytics tables are required.
"""
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.security import get_current_user, require_roles
from app.models.domain import Application, NicReview, User
from app.models.state import ApplicationState
from app.schemas.reports import (
    NicCodeCount,
    ReportsOverviewResponse,
    StageCount,
    StatusCount,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


# Groups of statuses the operator-facing dashboard surfaces.
_TERMINAL_SUCCESS_STATES = {
    ApplicationState.COMPLETED.value,
    ApplicationState.CERTIFICATE_READY.value,
    ApplicationState.SUBMITTED.value,
    ApplicationState.REGISTERED.value,
    ApplicationState.APPROVED.value,
}
_EXCEPTION_STATES = {
    ApplicationState.EXCEPTION.value,
    ApplicationState.DUPLICATE_PAN_DETECTED.value,
    ApplicationState.UAM_NOT_FOUND.value,
}


@router.get("/overview", response_model=ReportsOverviewResponse)
async def reports_overview(
    branch_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    )),
):
    """Top-level rollup: KPIs, status distribution, 7-day completions, top NIC codes.

    Branch scope: SUPER_ADMIN may pass ``?branch_id=`` or omit for all
    branches; everyone else is forced to their own branch.
    """
    if current_user.role == "SUPER_ADMIN":
        effective_branch_id = branch_id
    else:
        effective_branch_id = current_user.branch_id

    # Aggregate counts per status.
    counts_stmt = select(Application.status, func.count(Application.id))
    if effective_branch_id is not None:
        counts_stmt = counts_stmt.where(Application.branch_id == effective_branch_id)
    counts_stmt = counts_stmt.group_by(Application.status)
    status_rows = (await db.execute(counts_stmt)).all()

    status_counts: dict[str, int] = {row[0]: int(row[1]) for row in status_rows}

    total_applications = sum(status_counts.values())
    completed_applications = sum(
        status_counts.get(s, 0) for s in _TERMINAL_SUCCESS_STATES
    )
    exceptions = sum(status_counts.get(s, 0) for s in _EXCEPTION_STATES)
    pending_applications = max(total_applications - completed_applications - exceptions, 0)
    success_rate = (
        completed_applications / total_applications if total_applications else 0.0
    )

    # 7-day completions bucket — count applications whose updated_at crossed
    # into a terminal-success state in the last 7 days. Approximated by
    # counting all apps currently in those states whose updated_at >= now-7d
    # (good enough for the chart; precise per-day transitions would need
    # audit_log scanning which we skip here to keep the endpoint cheap).
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    completions_by_day: list[StageCount] = []
    if total_applications:
        completed_recent_stmt = select(Application.updated_at).where(
            Application.status.in_(_TERMINAL_SUCCESS_STATES),
            Application.updated_at >= seven_days_ago,
        )
        if effective_branch_id is not None:
            completed_recent_stmt = completed_recent_stmt.where(
                Application.branch_id == effective_branch_id
            )
        completed_dates = (await db.execute(completed_recent_stmt)).scalars().all()

        per_day: dict[str, int] = defaultdict(int)
        for d in completed_dates:
            key = d.astimezone(timezone.utc).date().isoformat()
            per_day[key] += 1

        day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        # Build 7 buckets oldest → newest.
        for offset in range(6, -1, -1):
            day = (now - timedelta(days=offset)).date()
            key = day.isoformat()
            label = day_labels[day.weekday()]
            completions_by_day.append(
                StageCount(key=key, label=label, count=per_day.get(key, 0))
            )

    # Average processing time (created_at → updated_at for terminal-success apps).
    avg_proc_seconds: Optional[float] = None
    proc_stmt = select(
        func.avg(
            func.extract("epoch", Application.updated_at - Application.created_at)
        )
    ).where(Application.status.in_(_TERMINAL_SUCCESS_STATES))
    if effective_branch_id is not None:
        proc_stmt = proc_stmt.where(Application.branch_id == effective_branch_id)
    avg_proc_seconds = (await db.execute(proc_stmt)).scalar_one_or_none()
    avg_processing_seconds: Optional[float] = (
        float(avg_proc_seconds) if avg_proc_seconds is not None else None
    )

    # Top 5 NIC codes — NicReview rows whose decision is APPROVE / OVERRIDE.
    # selected_codes is JSON list; we aggregate in Python (small bounded set —
    # reviewer decisions, not all-time audit).
    nic_stmt = select(NicReview.selected_codes, NicReview.decision)
    nic_rows = (await db.execute(nic_stmt)).all()
    code_counter: dict[str, int] = defaultdict(int)
    for codes, decision in nic_rows:
        if decision not in ("APPROVE", "OVERRIDE"):
            continue
        for c in (codes or []):
            code_counter[str(c)] += 1

    top_codes = sorted(code_counter.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_nic_codes: list[NicCodeCount] = []
    for code, count in top_codes:
        # First-line of the reviewer's justification as a stand-in description
        # (the NIC PDF isn't loaded server-side; this is good enough for the
        # reports row and consistent with the reviews-page rendering).
        desc_row = (
            await db.execute(
                select(NicReview.justification)
                .where(NicReview.selected_codes.contains([code]))
                .limit(1)
            )
        ).scalar_one_or_none()
        top_nic_codes.append(
            NicCodeCount(
                code=code,
                description=(desc_row.splitlines()[0] if desc_row else ""),
                count=count,
            )
        )

    status_distribution: list[StatusCount] = [
        StatusCount(status=s, count=c)
        for s, c in sorted(status_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return ReportsOverviewResponse(
        generated_at=now,
        total_applications=total_applications,
        completed_applications=completed_applications,
        pending_applications=pending_applications,
        exceptions=exceptions,
        success_rate=success_rate,
        average_processing_seconds=avg_processing_seconds,
        completions_by_day=completions_by_day,
        status_distribution=status_distribution,
        top_nic_codes=top_nic_codes,
    )