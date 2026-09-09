"""Tests for WorkflowOrchestrator, HumanCheckpointService, and Execution Graph."""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.domain import (
    Application,
    Branch,
    Client,
    HumanCheckpoint,
    User,
    Workflow,
    WorkflowExecution,
    WorkflowNodeExecution,
)
from app.models.state import ApplicationState
from app.services.human_checkpoint_service import HumanCheckpointService
from app.services.workflow_orchestrator import STANDARD_WORKFLOW_NODES, WorkflowOrchestrator


@pytest_asyncio.fixture
async def db():
    """Yield a session that auto-rolls back at the end of each test."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


async def _seed_app(db: AsyncSession) -> tuple[Application, Branch, Client, User]:
    branch = Branch(name="Orchestrator Branch", code=f"B{uuid.uuid4().hex[:6].upper()}", status="ACTIVE")
    db.add(branch)
    await db.flush()

    user = User(
        email=f"admin_{uuid.uuid4().hex[:6]}@taxla.in",
        name="Admin Test",
        password_hash="test_hash",
        role="SUPER_ADMIN",
        branch_id=branch.id,
        status="ACTIVE",
    )
    db.add(user)
    await db.flush()

    client = Client(
        branch_id=branch.id,
        business_name="Autonomous Tech Enterprises",
        applicant_name="Sunil Mittal",
        mobile_number="9876543210",
        pan_number=f"ABCDE{uuid.uuid4().hex[:4].upper()}F",
        aadhaar_number_hash="0" * 64,
    )
    db.add(client)
    await db.flush()

    app = Application(
        client_id=client.id,
        branch_id=branch.id,
        application_number=f"TX-{uuid.uuid4().hex[:6].upper()}",
        workflow_type="NEW_UDYAM",
        status=ApplicationState.NEW.value,
        assigned_to=user.id,
    )
    db.add(app)
    await db.flush()

    return app, branch, client, user


@pytest.mark.asyncio
async def test_get_or_create_execution_initializes_all_16_nodes(db: AsyncSession):
    app, branch, client, user = await _seed_app(db)

    exec_obj = await WorkflowOrchestrator.get_or_create_execution(
        application_id=app.id,
        db=db,
        user_id=user.id,
        trigger_source="DOCUMENT_UPLOAD",
    )

    assert exec_obj is not None
    assert exec_obj.application_id == app.id
    assert exec_obj.status == "RUNNING"

    # Verify all 16 standard nodes are initialized in database
    nodes_res = await db.execute(
        select(WorkflowNodeExecution).where(WorkflowNodeExecution.execution_id == exec_obj.id)
    )
    nodes = nodes_res.scalars().all()
    assert len(nodes) == 16

    node_ids = {n.node_id for n in nodes}
    for item in STANDARD_WORKFLOW_NODES:
        assert item["node_id"] in node_ids


@pytest.mark.asyncio
async def test_human_checkpoint_lifecycle(db: AsyncSession):
    app, branch, client, user = await _seed_app(db)

    exec_obj = await WorkflowOrchestrator.get_or_create_execution(
        application_id=app.id,
        db=db,
        user_id=user.id,
    )

    node_exec = await WorkflowOrchestrator.get_node_execution(exec_obj.id, "human_checkpoint", db)

    # 1. Create Checkpoint
    checkpoint = await HumanCheckpointService.create_checkpoint(
        execution_id=exec_obj.id,
        application_id=app.id,
        node_execution_id=node_exec.id if node_exec else None,
        checkpoint_type="OTP",
        title="Aadhaar OTP Required",
        prompt_message="Enter the 6-digit OTP",
        context_data={"aadhaar_suffix": "3210"},
        db=db,
    )

    assert checkpoint.status == "PENDING"
    assert checkpoint.checkpoint_type == "OTP"

    # Execution status should now reflect HUMAN_REQUIRED
    await db.refresh(exec_obj)
    assert exec_obj.status == "HUMAN_REQUIRED"

    # 2. Resolve Checkpoint
    resolved = await HumanCheckpointService.resolve_checkpoint(
        checkpoint_id=checkpoint.id,
        resolution_data={"otp_code": "123456"},
        user_id=user.id,
        db=db,
    )

    assert resolved.status == "RESOLVED"
    assert resolved.resolved_by == user.id
    assert resolved.resolution_data == {"otp_code": "123456"}

    # Execution status should now be restored to RUNNING
    await db.refresh(exec_obj)
    assert exec_obj.status == "RUNNING"


@pytest.mark.asyncio
async def test_execution_pause_resume_cancel(db: AsyncSession):
    app, branch, client, user = await _seed_app(db)

    exec_obj = await WorkflowOrchestrator.get_or_create_execution(
        application_id=app.id,
        db=db,
        user_id=user.id,
    )

    # Pause
    paused = await WorkflowOrchestrator.pause_execution(exec_obj.id, "Operator paused for inspection", db)
    assert paused.status == "PAUSED"

    # Resume
    resumed = await WorkflowOrchestrator.resume_execution(exec_obj.id, db, user.id)
    assert resumed.status == "RUNNING"

    # Cancel
    cancelled = await WorkflowOrchestrator.cancel_execution(exec_obj.id, "Test cancellation", db)
    assert cancelled.status == "CANCELLED"
