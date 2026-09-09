"""Generic Human Checkpoint Service for TAXLA Autonomous Platform.

Handles OTP, CAPTCHA, DATA_REVIEW, NIC_APPROVAL, FINAL_APPROVAL, and EXCEPTION checkpoints.
Durable persistence, real-time event broadcasting, and automatic workflow resumption.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.events import publish_event
from app.models.domain import Application, HumanCheckpoint, User, WorkflowExecution, WorkflowNodeExecution

logger = logging.getLogger("taxla.services.checkpoints")


class HumanCheckpointService:
    @staticmethod
    async def create_checkpoint(
        *,
        execution_id: uuid.UUID,
        application_id: uuid.UUID,
        node_execution_id: Optional[uuid.UUID],
        checkpoint_type: str,
        title: str,
        prompt_message: str,
        context_data: Optional[Dict[str, Any]] = None,
        db: AsyncSession,
    ) -> HumanCheckpoint:
        """Create and persist a human checkpoint, updating execution state and broadcasting events."""
        checkpoint = HumanCheckpoint(
            id=uuid.uuid4(),
            execution_id=execution_id,
            application_id=application_id,
            node_execution_id=node_execution_id,
            checkpoint_type=checkpoint_type,
            status="PENDING",
            title=title,
            prompt_message=prompt_message,
            context_data=context_data or {},
            created_at=datetime.now(timezone.utc),
        )
        db.add(checkpoint)

        # Update Execution status
        exec_res = await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
        workflow_exec = exec_res.scalars().first()
        if workflow_exec:
            workflow_exec.status = "HUMAN_REQUIRED"
            workflow_exec.updated_at = datetime.now(timezone.utc)

        # Update Node Execution status if provided
        if node_execution_id:
            node_res = await db.execute(select(WorkflowNodeExecution).where(WorkflowNodeExecution.id == node_execution_id))
            node_exec = node_res.scalars().first()
            if node_exec:
                node_exec.status = "HUMAN_REQUIRED"
                node_exec.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(checkpoint)

        # Broadcast real-time events
        event_payload = {
            "event": "CHECKPOINT_CREATED",
            "checkpoint_id": str(checkpoint.id),
            "execution_id": str(execution_id),
            "application_id": str(application_id),
            "checkpoint_type": checkpoint_type,
            "title": title,
            "prompt_message": prompt_message,
            "context_data": context_data or {},
            "status": "PENDING",
            "created_at": checkpoint.created_at.isoformat(),
        }

        try:
            r = aioredis.from_url(settings.REDIS_URL)
            await r.publish("taxla:updates", json.dumps(event_payload))
            await r.aclose()
        except Exception as e:
            logger.warning("Failed to publish CHECKPOINT_CREATED to taxla:updates: %s", e)

        await publish_event(event_payload)

        return checkpoint

    @staticmethod
    async def resolve_checkpoint(
        *,
        checkpoint_id: uuid.UUID,
        resolution_data: Dict[str, Any],
        user_id: Optional[uuid.UUID],
        db: AsyncSession,
    ) -> HumanCheckpoint:
        """Resolve a human checkpoint, record resolution data, and resume execution."""
        res = await db.execute(select(HumanCheckpoint).where(HumanCheckpoint.id == checkpoint_id))
        checkpoint = res.scalars().first()
        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")

        if checkpoint.status != "PENDING":
            raise ValueError(f"Checkpoint {checkpoint_id} is already in {checkpoint.status} status")

        checkpoint.status = "RESOLVED"
        checkpoint.resolved_at = datetime.now(timezone.utc)
        checkpoint.resolved_by = user_id
        checkpoint.resolution_data = resolution_data

        # Update Node Execution status
        if checkpoint.node_execution_id:
            node_res = await db.execute(select(WorkflowNodeExecution).where(WorkflowNodeExecution.id == checkpoint.node_execution_id))
            node_exec = node_res.scalars().first()
            if node_exec:
                node_exec.status = "RUNNING"
                node_exec.updated_at = datetime.now(timezone.utc)

        # Update Execution status
        exec_res = await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == checkpoint.execution_id))
        workflow_exec = exec_res.scalars().first()
        if workflow_exec:
            workflow_exec.status = "RUNNING"
            workflow_exec.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(checkpoint)

        # If checkpoint was OTP, also publish to Redis OTP channel for waiting Playwright workers
        if checkpoint.checkpoint_type == "OTP":
            otp_code = resolution_data.get("otp_code") or resolution_data.get("otp")
            if otp_code:
                try:
                    r = aioredis.from_url(settings.REDIS_URL)
                    await r.publish(f"otp_{checkpoint.application_id}", str(otp_code))
                    await r.aclose()
                except Exception as e:
                    logger.warning("Failed to publish OTP code to otp_%s: %s", checkpoint.application_id, e)

        # Broadcast resolution events
        event_payload = {
            "event": "CHECKPOINT_COMPLETED",
            "checkpoint_id": str(checkpoint.id),
            "execution_id": str(checkpoint.execution_id),
            "application_id": str(checkpoint.application_id),
            "checkpoint_type": checkpoint.checkpoint_type,
            "status": "RESOLVED",
            "resolved_at": checkpoint.resolved_at.isoformat() if checkpoint.resolved_at else None,
            "resolution_data": resolution_data,
        }

        try:
            r = aioredis.from_url(settings.REDIS_URL)
            await r.publish("taxla:updates", json.dumps(event_payload))
            await r.aclose()
        except Exception as e:
            logger.warning("Failed to publish CHECKPOINT_COMPLETED to taxla:updates: %s", e)

        await publish_event(event_payload)

        return checkpoint
