"""Workflow repository — encapsulates reads/writes for Workflow + WorkflowEvent.

Most callers should go through ``app.core.state_machine.transition`` which
already writes all four rows atomically. This repository is for:

  * ad-hoc reads (e.g. dashboard / audit tools querying workflow history),
  * code paths that need to write a WorkflowEvent WITHOUT changing the
    application state (e.g. a heartbeat, a screenshot, a state-payload
    update mid-transition),
  * admin tools that need to repair or migrate workflow rows.

Usage::

    repo = WorkflowRepository(db)
    workflow = await repo.get_workflow(application_id)
    events = await repo.list_events(workflow.id)
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Workflow, WorkflowEvent


class WorkflowRepository:
    """Async repository for Workflow + WorkflowEvent rows."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_workflow(self, application_id: uuid.UUID) -> Optional[Workflow]:
        stmt = select(Workflow).where(Workflow.application_id == application_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_events(
        self,
        workflow_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[WorkflowEvent]:
        """Return workflow events ordered oldest-first (chronological)."""
        stmt = (
            select(WorkflowEvent)
            .where(WorkflowEvent.workflow_id == workflow_id)
            .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_events_for_application(
        self,
        application_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[WorkflowEvent]:
        stmt = (
            select(WorkflowEvent)
            .where(WorkflowEvent.application_id == application_id)
            .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_event(
        self,
        workflow: Workflow,
        node_key: str,
        event_type: str,
        status: str,
        payload_json: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> WorkflowEvent:
        """Insert a WorkflowEvent row and flush so the caller gets the id.

        Use this when you need to record a workflow event without changing
        the application state (e.g. screenshot checkpoint, heartbeat).
        Prefer ``state_machine.transition`` for state-changing events so the
        Application row update, Workflow row update, WorkflowEvent insert,
        and AuditLog insert all happen in one transaction.
        """
        event = WorkflowEvent(
            workflow_id=workflow.id,
            application_id=workflow.application_id,
            node_key=node_key,
            event_type=event_type,
            status=status,
            payload_json=payload_json,
            error_code=error_code,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def update_context(
        self, workflow: Workflow, patch: Dict[str, Any]
    ) -> Workflow:
        """Merge ``patch`` into ``Workflow.context_json`` (in-session; caller commits)."""
        merged = {**(workflow.context_json or {}), **patch}
        workflow.context_json = merged
        return workflow

    async def set_resume_target(
        self, workflow: Workflow, resume_target: str
    ) -> Workflow:
        """Convenience: store the recovery target on the workflow context."""
        return await self.update_context(workflow, {"resume_target": resume_target})

    async def get_resume_target(self, workflow: Workflow) -> Optional[str]:
        """Return the stored resume target, or None if not set."""
        if not workflow.context_json:
            return None
        return workflow.context_json.get("resume_target")