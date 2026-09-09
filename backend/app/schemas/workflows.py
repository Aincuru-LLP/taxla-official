"""Phase 14 — Workflows summary schema.

Per-pipeline-stage count for the workflows overview page. Stages
collapse the 24-state machine into 5 operator-visible buckets.
"""
from typing import List

from pydantic import BaseModel


class WorkflowStageCount(BaseModel):
    key: str
    label: str
    description: str
    count: int


class WorkflowsSummaryResponse(BaseModel):
    stages: List[WorkflowStageCount]
    total_in_flight: int
