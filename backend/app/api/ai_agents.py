"""Phase 13 — AI Agents live-metrics API.

Three endpoint groups, one per agent:

  * ``GET /ai-agents/nic-matcher/metrics``   — counts + tier distribution +
    acceptance rate + top suggested codes + recent searches.
  * ``GET /ai-agents/validator/metrics``    — per-field pass/fail breakdown,
    review-decision distribution, recent failing fields.
  * ``GET /ai-agents/portal-driver/metrics`` — portal-run counts by status,
    success rate over time, queue depth (applications currently sitting in
    a portal-driver state), recent runs.

Data sources: all metrics are computed on-the-fly from existing tables
(``nic_suggestions``, ``extracted_data``, ``portal_sessions``,
``applications``, ``workflow_events``). No new tracking tables — the
existing rows already carry the signal we need, and a fresh-DB will
simply return zeros.

The endpoints are deliberately fast (a handful of aggregate queries each,
all indexed) so the frontend can poll every few seconds without putting
noticeable load on Postgres.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db as get_db
from app.core.security import get_current_user
from app.models.domain import (
    Application,
    ExtractedData,
    NICSuggestion,
    PortalSession,
    User,
)

logger = logging.getLogger("taxla.api.ai_agents")

router = APIRouter(prefix="/ai-agents", tags=["ai-agents"])


# Statuses that mean "the portal driver has the wheel right now". Used to
# compute the live queue depth for the portal-driver card.
_PORTAL_DRIVER_ACTIVE_STATUSES = (
    "READY_FOR_PORTAL",
    "PORTAL_RUNNING",
    "OTP_REQUIRED",
    "OTP_VERIFIED",
    "HUMAN_REVIEW",
    "SUBMITTING",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# ---------------------------------------------------------------------------
# NIC Code Matcher
# ---------------------------------------------------------------------------


@router.get("/nic-matcher/metrics")
async def nic_matcher_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate stats for the 3-tier NIC classifier.

    Top-level numbers are computed over the last 7 days; the same numbers
    over 24 h are exposed separately so the dashboard can show "today" vs
    "this week" without two endpoints.
    """
    since_24h = _since(1)
    since_7d = _since(7)

    # Total searches (a "search" = a NIC matching request; a single request
    # can produce multiple suggestion rows, so we group by application +
    # minute bucket via DISTINCT application_id over the window).
    total_24h = (
        await db.execute(
            select(func.count(func.distinct(NICSuggestion.application_id))).where(
                NICSuggestion.created_at >= since_24h
            )
        )
    ).scalar_one()
    total_7d = (
        await db.execute(
            select(func.count(func.distinct(NICSuggestion.application_id))).where(
                NICSuggestion.created_at >= since_7d
            )
        )
    ).scalar_one()

    # Acceptance rate = approved suggestions / total suggestions over 7d.
    approval_stmt = select(
        func.count(NICSuggestion.id).label("total"),
        func.sum(case((NICSuggestion.approved.is_(True), 1), else_=0)).label(
            "approved"
        ),
    ).where(NICSuggestion.created_at >= since_7d)
    row = (await db.execute(approval_stmt)).one()
    total_suggestions = int(row.total or 0)
    approved_suggestions = int(row.approved or 0)
    acceptance_rate = (
        round(approved_suggestions / total_suggestions, 4) if total_suggestions else 0.0
    )

    # Tier distribution. We don't tag suggestions with a tier at write time
    # (would require a schema change), so we infer it from ``confidence`` +
    # ``rationale`` heuristics that match what ``nic_service`` writes.
    tier_stmt = select(NICSuggestion.confidence, NICSuggestion.rationale).where(
        NICSuggestion.created_at >= since_7d
    )
    raw_rows = (await db.execute(tier_stmt)).all()
    tier_counts = Counter({"keyword": 0, "vector": 0, "llm": 0})
    for conf, rationale in raw_rows:
        r = (rationale or "").lower()
        if "keyword" in r:
            tier_counts["keyword"] += 1
        elif "vector" in r or "cosine" in r:
            tier_counts["vector"] += 1
        else:
            tier_counts["llm"] += 1
    tier_total = sum(tier_counts.values()) or 1
    tier_distribution = {
        k: round(v / tier_total, 4) for k, v in tier_counts.items()
    }

    # Top 5 suggested 5-digit codes over the last 7 days.
    top_codes_stmt = (
        select(
            NICSuggestion.nic_code_5digit,
            NICSuggestion.description,
            func.count(NICSuggestion.id).label("hits"),
        )
        .where(NICSuggestion.created_at >= since_7d)
        .group_by(NICSuggestion.nic_code_5digit, NICSuggestion.description)
        .order_by(func.count(NICSuggestion.id).desc())
        .limit(5)
    )
    top_codes = [
        {"code": c, "description": d, "count": int(n)}
        for c, d, n in (await db.execute(top_codes_stmt)).all()
    ]

    # Recent activity feed — 8 latest suggestion rows across the branch.
    recent_stmt = (
        select(
            NICSuggestion.id,
            NICSuggestion.application_id,
            NICSuggestion.nic_code_5digit,
            NICSuggestion.description,
            NICSuggestion.confidence,
            NICSuggestion.approved,
            NICSuggestion.created_at,
        )
        .order_by(NICSuggestion.created_at.desc())
        .limit(8)
    )
    recent = [
        {
            "id": str(r.id),
            "application_id": str(r.application_id),
            "code": r.nic_code_5digit,
            "description": r.description,
            "confidence": float(r.confidence) if r.confidence is not None else None,
            "approved": bool(r.approved),
            "at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in (await db.execute(recent_stmt)).all()
    ]

    return {
        "window_24h_searches": int(total_24h or 0),
        "window_7d_searches": int(total_7d or 0),
        "acceptance_rate_7d": acceptance_rate,
        "tier_distribution": tier_distribution,
        "top_codes": top_codes,
        "recent": recent,
    }


# ---------------------------------------------------------------------------
# Document Validator
# ---------------------------------------------------------------------------


@router.get("/validator/metrics")
async def validator_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-field pass/fail stats for the format validators."""
    since_24h = _since(1)
    since_7d = _since(7)

    # Total fields validated in window.
    total_7d = (
        await db.execute(
            select(func.count(ExtractedData.id)).where(
                ExtractedData.created_at >= since_7d
            )
        )
    ).scalar_one()
    total_24h = (
        await db.execute(
            select(func.count(ExtractedData.id)).where(
                ExtractedData.created_at >= since_24h
            )
        )
    ).scalar_one()

    # Review-decision distribution (PASS / REVIEW / FAIL / UNVERIFIED).
    decision_stmt = (
        select(ExtractedData.review_decision, func.count(ExtractedData.id))
        .where(ExtractedData.created_at >= since_7d)
        .group_by(ExtractedData.review_decision)
    )
    decisions = {
        (k or "UNVERIFIED"): int(v) for k, v in (await db.execute(decision_stmt)).all()
    }
    pass_count = decisions.get("PASS", 0)
    fail_count = decisions.get("FAIL", 0)
    review_count = decisions.get("REVIEW", 0)
    pass_rate = (
        round(pass_count / (pass_count + fail_count + review_count), 4)
        if (pass_count + fail_count + review_count)
        else 0.0
    )

    # Failures by field — how many rows have a FAIL decision per field_name.
    fail_by_field_stmt = (
        select(ExtractedData.field_name, func.count(ExtractedData.id))
        .where(
            ExtractedData.review_decision == "FAIL",
            ExtractedData.created_at >= since_7d,
        )
        .group_by(ExtractedData.field_name)
        .order_by(func.count(ExtractedData.id).desc())
        .limit(8)
    )
    failures_by_field = {
        k: int(v) for k, v in (await db.execute(fail_by_field_stmt)).all()
    }

    # Avg confidence (final_confidence) over 7d for the headline "OCR quality" stat.
    avg_conf = (
        await db.execute(
            select(func.avg(ExtractedData.final_confidence)).where(
                ExtractedData.final_confidence.is_not(None),
                ExtractedData.created_at >= since_7d,
            )
        )
    ).scalar_one()

    # Recent failures — last 6 FAIL rows.
    recent_fail_stmt = (
        select(
            ExtractedData.field_name,
            ExtractedData.field_value,
            ExtractedData.validation_errors,
            ExtractedData.application_id,
            ExtractedData.created_at,
        )
        .where(ExtractedData.review_decision == "FAIL")
        .order_by(ExtractedData.created_at.desc())
        .limit(6)
    )
    recent_failures = [
        {
            "field": r.field_name,
            "value": (r.field_value or "")[:64],
            "errors": (r.validation_errors or [])[:3] if isinstance(r.validation_errors, list) else [],
            "application_id": str(r.application_id),
            "at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in (await db.execute(recent_fail_stmt)).all()
    ]

    return {
        "window_24h_validations": int(total_24h or 0),
        "window_7d_validations": int(total_7d or 0),
        "pass_rate_7d": pass_rate,
        "decisions": decisions,
        "failures_by_field": failures_by_field,
        "avg_confidence_7d": round(float(avg_conf), 4) if avg_conf is not None else None,
        "recent_failures": recent_failures,
    }


# ---------------------------------------------------------------------------
# Udyam Portal Driver
# ---------------------------------------------------------------------------


@router.get("/portal-driver/metrics")
async def portal_driver_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Portal driver throughput, queue depth, and recent runs."""
    since_24h = _since(1)
    since_7d = _since(7)

    # Total portal sessions ever started; over 7d; over 24h.
    total_stmt = select(func.count(PortalSession.id))
    total_7d_stmt = select(func.count(PortalSession.id)).where(
        PortalSession.created_at >= since_7d
    )
    total_24h_stmt = select(func.count(PortalSession.id)).where(
        PortalSession.created_at >= since_24h
    )
    total_all = int((await db.execute(total_stmt)).scalar_one() or 0)
    total_7d = int((await db.execute(total_7d_stmt)).scalar_one() or 0)
    total_24h = int((await db.execute(total_24h_stmt)).scalar_one() or 0)

    # Status distribution across all sessions.
    status_stmt = (
        select(PortalSession.session_status, func.count(PortalSession.id))
        .group_by(PortalSession.session_status)
    )
    statuses = {
        k: int(v) for k, v in (await db.execute(status_stmt)).all()
    }

    # Queue depth — applications currently parked in a portal-driver state.
    queue_stmt = select(func.count(Application.id)).where(
        Application.status.in_(_PORTAL_DRIVER_ACTIVE_STATUSES)
    )
    queue_depth = int((await db.execute(queue_stmt)).scalar_one() or 0)

    # Success rate — sessions that reached SUBMITTED vs hit EXCEPTION.
    submitted_q = select(func.count(Application.id)).where(
        Application.status == "SUBMITTED",
        Application.updated_at >= since_7d,
    )
    submitted = int((await db.execute(submitted_q)).scalar_one() or 0)
    exception_q = select(func.count(Application.id)).where(
        Application.status == "EXCEPTION",
        Application.updated_at >= since_7d,
    )
    exception_count = int((await db.execute(exception_q)).scalar_one() or 0)
    completed = submitted + exception_count
    success_rate = round(submitted / completed, 4) if completed else 0.0

    # Recent portal runs — last 8 sessions, joined to application for context.
    recent_stmt = (
        select(
            PortalSession.id,
            PortalSession.application_id,
            PortalSession.session_status,
            PortalSession.last_checkpoint,
            PortalSession.error_log,
            PortalSession.created_at,
            PortalSession.updated_at,
            Application.application_number,
            Application.status.label("app_status"),
        )
        .join(Application, Application.id == PortalSession.application_id)
        .order_by(PortalSession.created_at.desc())
        .limit(8)
    )
    recent_runs = [
        {
            "id": str(r.id),
            "application_id": str(r.application_id),
            "application_number": r.application_number,
            "session_status": r.session_status,
            "app_status": r.app_status,
            "last_checkpoint": r.last_checkpoint,
            "error_preview": (r.error_log or "")[:160] if r.error_log else None,
            "started_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in (await db.execute(recent_stmt)).all()
    ]

    return {
        "window_24h_runs": total_24h,
        "window_7d_runs": total_7d,
        "total_runs": total_all,
        "queue_depth": queue_depth,
        "status_distribution": statuses,
        "success_rate_7d": success_rate,
        "completed_7d": completed,
        "submitted_7d": submitted,
        "exception_7d": exception_count,
        "recent_runs": recent_runs,
    }


@router.get("/portal-driver/queue")
async def portal_driver_queue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List applications currently in a portal-driver state."""
    stmt = (
        select(
            Application.id,
            Application.application_number,
            Application.status,
            Application.updated_at,
        )
        .where(Application.status.in_(_PORTAL_DRIVER_ACTIVE_STATUSES))
        .order_by(Application.updated_at.desc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(r.id),
            "application_number": r.application_number,
            "status": r.status,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
