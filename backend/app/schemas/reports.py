"""Phase 14 — Analytics / reports overview schemas.

Aggregates the ``applications`` table into the operator-facing KPIs
that the reports page renders. Everything here is derived from
the application lifecycle (created_at, status, audit timestamps)
so a separate analytics table isn't required.
"""
from datetime import datetime
from typing import List

from pydantic import BaseModel


class StageCount(BaseModel):
    """Count of applications currently in one bucket of the pipeline."""

    key: str
    label: str
    count: int


class StatusCount(BaseModel):
    """Count of applications currently in a single application state."""

    status: str
    count: int


class NicCodeCount(BaseModel):
    """Count of times a 5-digit NIC code has been approved by reviewers."""

    code: str
    description: str
    count: int


class ReportsOverviewResponse(BaseModel):
    """Top-level rollup for the reports page.

    All counts are branch-scoped (or global for SUPER_ADMIN) and live
    as of ``generated_at``.
    """

    generated_at: datetime
    total_applications: int
    completed_applications: int
    pending_applications: int
    exceptions: int
    success_rate: float  # 0.0–1.0 = completed / total
    average_processing_seconds: float | None  # None if no completed apps yet

    # Last 7 days of completions, oldest → newest, one bucket per day.
    completions_by_day: List[StageCount]

    # Distribution of applications across pipeline stages.
    status_distribution: List[StatusCount]

    # Top 5 NIC codes approved by reviewers (most-used activities).
    top_nic_codes: List[NicCodeCount]
