"""API Router for Workflow Executions, Visualizer Graphs, and Human Checkpoints."""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_async_db
from app.core.security import assert_branch_scope, get_current_user, require_roles
from app.models.domain import Application, Document, HumanCheckpoint, User, WorkflowExecution, WorkflowNodeExecution
from app.services.human_checkpoint_service import HumanCheckpointService
from app.services.workflow_orchestrator import WorkflowOrchestrator

router = APIRouter(tags=["Executions & Automation Visualizer"])


class CheckpointResolveRequest(BaseModel):
    resolution_data: Dict[str, Any]


class ActionReasonRequest(BaseModel):
    reason: Optional[str] = "Manual operator intervention"


class NodeExecutionResponse(BaseModel):
    id: uuid.UUID
    execution_id: uuid.UUID
    node_id: str
    node_label: str
    node_type: str
    status: str
    attempt: int
    max_attempts: int
    worker_id: Optional[str] = None
    input_summary: Optional[Dict[str, Any]] = None
    output_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    logs_text: Optional[str] = None
    screenshot_path: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class CheckpointResponse(BaseModel):
    id: uuid.UUID
    execution_id: uuid.UUID
    application_id: uuid.UUID
    node_execution_id: Optional[uuid.UUID] = None
    checkpoint_type: str
    status: str
    title: str
    prompt_message: str
    context_data: Optional[Dict[str, Any]] = None
    resolution_data: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ExecutionGraphResponse(BaseModel):
    execution_id: uuid.UUID
    application_id: uuid.UUID
    workflow_version: str
    status: str
    current_node_id: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    trigger_source: str
    error_message: Optional[str] = None
    nodes: List[NodeExecutionResponse]
    checkpoints: List[CheckpointResponse]
    live_screenshot_url: Optional[str] = None


@router.get(
    "/applications/{application_id}/automation/execution",
    response_model=ExecutionGraphResponse,
    dependencies=[Depends(require_roles("OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"))],
)
async def get_application_execution_graph(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full reload-safe visualizer execution graph for an application."""
    app_res = await db.execute(select(Application).where(Application.id == application_id))
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    exec_res = await db.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.application_id == application_id)
        .options(
            selectinload(WorkflowExecution.node_executions),
            selectinload(WorkflowExecution.checkpoints),
        )
        .order_by(WorkflowExecution.started_at.desc())
    )
    execution = exec_res.scalars().first()

    if not execution:
        # Auto-initialize execution so the visualizer always has a graph
        execution = await WorkflowOrchestrator.get_or_create_execution(application_id, db, user_id=current_user.id)
        exec_res = await db.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.id == execution.id)
            .options(
                selectinload(WorkflowExecution.node_executions),
                selectinload(WorkflowExecution.checkpoints),
            )
        )
        execution = exec_res.scalars().first()

    # Check if execution is fresh and pending document processing
    first_node = next((n for n in (execution.node_executions or []) if n.node_id == "doc_received"), None)
    if execution.status == "RUNNING" and first_node and first_node.status == "WAITING":
        doc_stmt = (
            select(Document)
            .where(Document.application_id == application_id)
            .order_by(Document.created_at.desc())
            .limit(1)
        )
        doc_res = await db.execute(doc_stmt)
        latest_doc = doc_res.scalars().first()
        if latest_doc:
            async def _run_detached_orchestrator(app_id: uuid.UUID, doc_id: uuid.UUID, uid: Optional[uuid.UUID]):
                from app.core.database import AsyncSessionLocal
                try:
                    async with AsyncSessionLocal() as session:
                        await WorkflowOrchestrator.process_document_pipeline(
                            application_id=app_id,
                            document_id=doc_id,
                            db=session,
                            user_id=uid,
                        )
                except Exception as err:
                    print(f"Error in detached pipeline: {err}")

            import asyncio
            asyncio.create_task(_run_detached_orchestrator(application_id, latest_doc.id, current_user.id))

    live_screenshot = None
    live_path = os.path.join(settings.DEBUG_SCREENSHOTS_DIR, f"{application_id}_live.png")
    if os.path.exists(live_path):
        live_screenshot = f"/api/v1/applications/{application_id}/automation/screenshot/live"

    nodes_data = [
        NodeExecutionResponse(
            id=n.id,
            execution_id=n.execution_id,
            node_id=n.node_id,
            node_label=n.node_label,
            node_type=n.node_type,
            status=n.status,
            attempt=n.attempt,
            max_attempts=n.max_attempts,
            worker_id=n.worker_id,
            input_summary=n.input_summary,
            output_summary=n.output_summary,
            error_message=n.error_message,
            logs_text=n.logs_text,
            screenshot_path=n.screenshot_path,
            started_at=n.started_at.isoformat() if n.started_at else None,
            completed_at=n.completed_at.isoformat() if n.completed_at else None,
            duration_seconds=float(n.duration_seconds) if n.duration_seconds else None,
        )
        for n in (execution.node_executions or [])
    ]

    checkpoints_data = [
        CheckpointResponse(
            id=c.id,
            execution_id=c.execution_id,
            application_id=c.application_id,
            node_execution_id=c.node_execution_id,
            checkpoint_type=c.checkpoint_type,
            status=c.status,
            title=c.title,
            prompt_message=c.prompt_message,
            context_data=c.context_data,
            resolution_data=c.resolution_data,
            created_at=c.created_at.isoformat() if c.created_at else None,
            resolved_at=c.resolved_at.isoformat() if c.resolved_at else None,
        )
        for c in (execution.checkpoints or [])
    ]

    return ExecutionGraphResponse(
        execution_id=execution.id,
        application_id=execution.application_id,
        workflow_version=execution.workflow_version,
        status=execution.status,
        current_node_id=execution.current_node_id,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        duration_seconds=float(execution.duration_seconds) if execution.duration_seconds else None,
        trigger_source=execution.trigger_source,
        error_message=execution.error_message,
        nodes=nodes_data,
        checkpoints=checkpoints_data,
        live_screenshot_url=live_screenshot,
    )


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionGraphResponse,
    dependencies=[Depends(require_roles("OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"))],
)
async def get_execution_by_id(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve execution by execution ID."""
    exec_res = await db.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.id == execution_id)
        .options(
            selectinload(WorkflowExecution.node_executions),
            selectinload(WorkflowExecution.checkpoints),
        )
    )
    execution = exec_res.scalars().first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return await get_application_execution_graph(execution.application_id, db, current_user)


@router.get(
    "/executions/{execution_id}/nodes/{node_id}",
    response_model=NodeExecutionResponse,
    dependencies=[Depends(require_roles("OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"))],
)
async def get_execution_node_detail(
    execution_id: uuid.UUID,
    node_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get full details, logs, output telemetry, and diagnostics for one node."""
    node = await WorkflowOrchestrator.get_node_execution(execution_id, node_id, db)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found in execution")

    return NodeExecutionResponse(
        id=node.id,
        execution_id=node.execution_id,
        node_id=node.node_id,
        node_label=node.node_label,
        node_type=node.node_type,
        status=node.status,
        attempt=node.attempt,
        max_attempts=node.max_attempts,
        worker_id=node.worker_id,
        input_summary=node.input_summary,
        output_summary=node.output_summary,
        error_message=node.error_message,
        logs_text=node.logs_text,
        screenshot_path=node.screenshot_path,
        started_at=node.started_at.isoformat() if node.started_at else None,
        completed_at=node.completed_at.isoformat() if node.completed_at else None,
        duration_seconds=float(node.duration_seconds) if node.duration_seconds else None,
    )


@router.post(
    "/executions/{execution_id}/pause",
    dependencies=[Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN"))],
)
async def pause_execution(
    execution_id: uuid.UUID,
    payload: Optional[ActionReasonRequest] = None,
    db: AsyncSession = Depends(get_async_db),
):
    reason = payload.reason if payload else "Operator pause"
    try:
        updated = await WorkflowOrchestrator.pause_execution(execution_id, reason, db)
        return {"success": True, "status": updated.status, "message": "Execution paused."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/executions/{execution_id}/resume",
    dependencies=[Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN"))],
)
async def resume_execution(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    try:
        updated = await WorkflowOrchestrator.resume_execution(execution_id, db, user_id=current_user.id)
        return {"success": True, "status": updated.status, "message": "Execution resumed."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/executions/{execution_id}/cancel",
    dependencies=[Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN"))],
)
async def cancel_execution(
    execution_id: uuid.UUID,
    payload: Optional[ActionReasonRequest] = None,
    db: AsyncSession = Depends(get_async_db),
):
    reason = payload.reason if payload else "Operator cancellation"
    try:
        updated = await WorkflowOrchestrator.cancel_execution(execution_id, reason, db)
        return {"success": True, "status": updated.status, "message": "Execution cancelled."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/checkpoints/{checkpoint_id}/resolve",
    dependencies=[Depends(require_roles("OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"))],
)
async def resolve_checkpoint(
    checkpoint_id: uuid.UUID,
    payload: CheckpointResolveRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve a human checkpoint (OTP, CAPTCHA, Review, etc.) and auto-resume workflow."""
    try:
        checkpoint = await HumanCheckpointService.resolve_checkpoint(
            checkpoint_id=checkpoint_id,
            resolution_data=payload.resolution_data,
            user_id=current_user.id,
            db=db,
        )
        return {
            "success": True,
            "checkpoint_id": str(checkpoint.id),
            "status": checkpoint.status,
            "message": "Checkpoint resolved successfully. Workflow resumed.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/applications/{application_id}/automation/screenshot/live")
async def get_live_screenshot(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Stream live Playwright screenshot for the Automation Visualizer."""
    live_path = os.path.join(settings.DEBUG_SCREENSHOTS_DIR, f"{application_id}_live.png")
    if not os.path.exists(live_path):
        # Look for any debug screenshot
        debug_dir = settings.DEBUG_SCREENSHOTS_DIR
        for f in os.listdir(debug_dir) if os.path.exists(debug_dir) else []:
            if f.startswith(str(application_id)) and f.endswith(".png"):
                live_path = os.path.join(debug_dir, f)
                break

    if not os.path.exists(live_path):
        raise HTTPException(status_code=404, detail="No live screenshot available yet")

    return FileResponse(
        path=live_path,
        media_type="image/png",
        content_disposition_type="inline",
    )
