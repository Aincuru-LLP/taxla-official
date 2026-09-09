"""Tests for the application state machine and the workflow engine writes
emitted by ``transition()``.

Covers Phase 03 deliverables:
  * transition() writes Application.status + Workflow.current_node +
    WorkflowEvent + AuditLog in one session (caller commits).
  * All 6 missing states from input requirmentsv2.md §39 are mapped.
  * RESUME bypass is gone; EXCEPTION → resume_target is the only recovery
    path, and resume_target must match the new_state.
  * Illegal transitions raise HTTP 409.

Run: pytest backend/tests/test_state_machine.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402 — NullPool in test mode
from app.core.state_machine import (  # noqa: E402
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    transition,
)
from app.models.domain import (  # noqa: E402
    Application,
    AuditLog,
    Branch,
    Client,
    User,
    Workflow,
    WorkflowEvent,
)
from app.models.domain import Base  # noqa: E402
from app.models.state import ApplicationState  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Create all tables once per test session (idempotent — only creates
    missing ones). Tests roll back individual writes so the DB stays clean."""
    from app.core.database import async_engine
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db():
    """Yield a session that auto-rolls back at the end of each test."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


async def _seed_minimal_app(db: AsyncSession, *, start_state: str = ApplicationState.NEW.value) -> tuple[Application, Branch, Client]:
    """Insert a branch + client + application (+ workflow) for tests."""
    branch = Branch(name="Test Branch", code=f"T{uuid.uuid4().hex[:8].upper()}", status="ACTIVE")
    db.add(branch)
    await db.flush()

    client = Client(
        branch_id=branch.id,
        business_name="Test Co",
        applicant_name="Test Applicant",
        mobile_number="9999999999",
        pan_number=f"ABCDE{uuid.uuid4().hex[:4].upper()}",
        aadhaar_number_hash="0" * 64,
    )
    db.add(client)
    await db.flush()

    app = Application(
        client_id=client.id,
        branch_id=branch.id,
        application_number=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        status=start_state,
    )
    db.add(app)
    await db.flush()

    workflow = Workflow(
        application_id=app.id,
        current_node=start_state,
        status="RUNNING",
        context_json={},
    )
    db.add(workflow)
    await db.flush()
    # Re-load the app with workflow relationship populated
    await db.refresh(app)
    return app, branch, client


# ---------------------------------------------------------------------------
# Happy-path: transition writes the right rows
# ---------------------------------------------------------------------------


async def test_transition_writes_application_workflow_event_audit(db):
    app, _, _ = await _seed_minimal_app(db)

    await transition(app, ApplicationState.DOCUMENTS_UPLOADED.value, None, db)
    await db.commit()

    assert app.status == ApplicationState.DOCUMENTS_UPLOADED.value

    # Query workflow + events + audits explicitly (avoids lazy-load in async).
    workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app.id)
        )
    ).scalars().one()
    assert workflow.current_node == ApplicationState.DOCUMENTS_UPLOADED.value
    assert workflow.status == "RUNNING"

    events = (
        await db.execute(
            select(WorkflowEvent).where(WorkflowEvent.application_id == app.id)
        )
    ).scalars().all()
    assert len(events) == 1
    e = events[0]
    assert e.node_key == ApplicationState.DOCUMENTS_UPLOADED.value
    assert e.event_type == "ENTERED"
    assert e.status == ApplicationState.DOCUMENTS_UPLOADED.value
    assert e.error_code is None
    assert e.payload_json["from_state"] == ApplicationState.NEW.value
    assert e.payload_json["to_state"] == ApplicationState.DOCUMENTS_UPLOADED.value

    audits = (
        await db.execute(
            select(AuditLog).where(AuditLog.application_id == app.id)
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].action == f"STATE_TRANSITION_{ApplicationState.DOCUMENTS_UPLOADED.value}"


async def test_transition_failure_emits_failed_event_with_error_code(db):
    app, _, _ = await _seed_minimal_app(
        db, start_state=ApplicationState.PORTAL_RUNNING.value
    )

    await transition(
        app,
        ApplicationState.EXCEPTION.value,
        None,
        db,
        error_code="OTP_TIMEOUT",
    )
    await db.commit()

    workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app.id)
        )
    ).scalars().one()
    assert workflow.status == "EXCEPTION"

    events = (
        await db.execute(
            select(WorkflowEvent).where(WorkflowEvent.application_id == app.id)
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "FAILED"
    assert events[0].error_code == "OTP_TIMEOUT"
    assert events[0].node_key == ApplicationState.EXCEPTION.value


async def test_transition_to_completed_marks_workflow_completed(db):
    app, _, _ = await _seed_minimal_app(
        db, start_state=ApplicationState.CERTIFICATE_READY.value
    )

    await transition(app, ApplicationState.COMPLETED.value, None, db)
    await db.commit()

    workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app.id)
        )
    ).scalars().one()
    assert workflow.status == "COMPLETED"

    events = (
        await db.execute(
            select(WorkflowEvent).where(WorkflowEvent.application_id == app.id)
        )
    ).scalars().all()
    assert events[0].event_type == "COMPLETED"
    assert ApplicationState.COMPLETED.value in TERMINAL_STATES


# ---------------------------------------------------------------------------
# Validation: illegal transitions
# ---------------------------------------------------------------------------


async def test_illegal_transition_raises_409(db):
    app, _, _ = await _seed_minimal_app(db)

    # NEW → READY_FOR_PORTAL is not legal (skips DOCUMENTS_UPLOADED + PROCESSING
    # + EXTRACTED + VALIDATION + NIC_REVIEW).
    with pytest.raises(HTTPException) as exc:
        await transition(app, ApplicationState.READY_FOR_PORTAL.value, None, db)
    assert exc.value.status_code == 409


async def test_no_bypass_from_resume_state(db):
    """RESUME state has no outgoing transitions — bypass is removed."""
    app, _, _ = await _seed_minimal_app(
        db, start_state=ApplicationState.RESUME.value
    )

    with pytest.raises(HTTPException) as exc:
        await transition(app, ApplicationState.PROCESSING.value, None, db)
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Resume target: EXCEPTION → resume_target
# ---------------------------------------------------------------------------


async def test_exception_to_resume_target_requires_matching_argument(db):
    app, _, _ = await _seed_minimal_app(
        db, start_state=ApplicationState.EXCEPTION.value
    )
    # Pre-seed the workflow context with a stored resume target.
    workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app.id)
        )
    ).scalars().one()
    workflow.context_json = {"resume_target": ApplicationState.PROCESSING.value}
    await db.flush()

    # Without resume_target → 409.
    with pytest.raises(HTTPException) as exc:
        await transition(app, ApplicationState.PROCESSING.value, None, db)
    assert exc.value.status_code == 409

    # With wrong resume_target → 409.
    with pytest.raises(HTTPException) as exc:
        await transition(
            app, ApplicationState.PROCESSING.value, None, db,
            resume_target=ApplicationState.OTP_REQUIRED.value,
        )
    assert exc.value.status_code == 409


async def test_exception_to_resume_target_with_matching_argument_succeeds(db):
    app, _, _ = await _seed_minimal_app(
        db, start_state=ApplicationState.EXCEPTION.value
    )
    workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app.id)
        )
    ).scalars().one()
    workflow.context_json = {"resume_target": ApplicationState.PROCESSING.value}
    await db.flush()

    await transition(
        app,
        ApplicationState.PROCESSING.value,
        None,
        db,
        resume_target=ApplicationState.PROCESSING.value,
    )
    await db.commit()

    assert app.status == ApplicationState.PROCESSING.value
    workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app.id)
        )
    ).scalars().one()
    assert workflow.current_node == ApplicationState.PROCESSING.value
    assert workflow.status == "RUNNING"


async def test_entering_exception_persists_resume_target_to_context(db):
    """When you transition INTO EXCEPTION, the resume_target (if passed)
    is stored on the workflow context for later recovery."""
    app, _, _ = await _seed_minimal_app(
        db, start_state=ApplicationState.PORTAL_RUNNING.value
    )

    await transition(
        app,
        ApplicationState.EXCEPTION.value,
        None,
        db,
        error_code="PLAYWRIGHT_FAILURE",
        resume_target=ApplicationState.OTP_REQUIRED.value,
    )
    await db.commit()

    workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app.id)
        )
    ).scalars().one()
    assert workflow.context_json.get("resume_target") == ApplicationState.OTP_REQUIRED.value


# ---------------------------------------------------------------------------
# Newly mapped states from input requirmentsv2.md §39
# ---------------------------------------------------------------------------


def test_all_six_missing_states_are_mapped():
    """VALID_TRANSITIONS must include all 6 new states."""
    new_states = [
        ApplicationState.AADHAAR_OTP.value,
        ApplicationState.PAN_VERIFICATION.value,
        ApplicationState.DATA_VERIFICATION.value,
        ApplicationState.REGISTERED.value,
        ApplicationState.DUPLICATE_PAN_DETECTED.value,
        ApplicationState.UAM_NOT_FOUND.value,
    ]
    for s in new_states:
        assert s in VALID_TRANSITIONS, f"{s} missing from VALID_TRANSITIONS"


def test_aadhaar_otp_reachable_from_submitted():
    assert ApplicationState.AADHAAR_OTP.value in VALID_TRANSITIONS[
        ApplicationState.SUBMITTED.value
    ]


def test_pan_verification_follows_aadhaar_otp():
    assert ApplicationState.PAN_VERIFICATION.value in VALID_TRANSITIONS[
        ApplicationState.AADHAAR_OTP.value
    ]


def test_registered_progresses_to_certificate_ready():
    assert ApplicationState.CERTIFICATE_READY.value in VALID_TRANSITIONS[
        ApplicationState.REGISTERED.value
    ]


def test_duplicate_pan_detected_is_dead_end_except_exception():
    """DUPLICATE_PAN_DETECTED can only escape to EXCEPTION (for human review)."""
    successors = VALID_TRANSITIONS[ApplicationState.DUPLICATE_PAN_DETECTED.value]
    assert successors == [ApplicationState.EXCEPTION.value]


def test_uam_not_found_is_dead_end_except_exception():
    successors = VALID_TRANSITIONS[ApplicationState.UAM_NOT_FOUND.value]
    assert successors == [ApplicationState.EXCEPTION.value]


# ---------------------------------------------------------------------------
# Phase 04: VALIDATION_REVIEW + HUMAN_REVIEW_REQUIRED paths
# ---------------------------------------------------------------------------


def test_validation_branches_to_nic_review_high_confidence():
    successors = VALID_TRANSITIONS[ApplicationState.VALIDATION.value]
    assert ApplicationState.NIC_REVIEW.value in successors


def test_validation_branches_to_validation_review_medium_confidence():
    successors = VALID_TRANSITIONS[ApplicationState.VALIDATION.value]
    assert ApplicationState.VALIDATION_REVIEW.value in successors


def test_validation_branches_to_human_review_required_low_confidence():
    successors = VALID_TRANSITIONS[ApplicationState.VALIDATION.value]
    assert ApplicationState.HUMAN_REVIEW_REQUIRED.value in successors


def test_validation_review_approves_to_nic_review():
    successors = VALID_TRANSITIONS[ApplicationState.VALIDATION_REVIEW.value]
    assert ApplicationState.NIC_REVIEW.value in successors


def test_validation_review_rejects_to_human_review_required():
    successors = VALID_TRANSITIONS[ApplicationState.VALIDATION_REVIEW.value]
    assert ApplicationState.HUMAN_REVIEW_REQUIRED.value in successors


def test_human_review_required_re_uploads_to_documents_uploaded():
    successors = VALID_TRANSITIONS[ApplicationState.HUMAN_REVIEW_REQUIRED.value]
    assert ApplicationState.DOCUMENTS_UPLOADED.value in successors


# ---------------------------------------------------------------------------
# Atomicity: failure mid-transition rolls back the whole session
# ---------------------------------------------------------------------------


async def test_atomicity_failure_rolls_back_all_four_writes(db):
    """If the WorkflowEvent insert blows up (e.g. a constraint violation),
    the session rolls back so no WorkflowEvent / AuditLog / Workflow row
    changes are persisted. The Application.status change is also reverted.
    """
    app, _, _ = await _seed_minimal_app(db)
    app_id = app.id

    # Commit the seed so it survives the test's own rollback below.
    await db.commit()

    original_workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app_id)
        )
    ).scalars().one()
    original_workflow_node = original_workflow.current_node

    # Force a failure by patching WorkflowEvent to raise on construction.
    import app.core.state_machine as sm

    class _BoomEvent:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("simulated insert failure")

    original_event = sm.WorkflowEvent
    sm.WorkflowEvent = _BoomEvent  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError):
            await transition(app, ApplicationState.DOCUMENTS_UPLOADED.value, None, db)
        await db.rollback()
    finally:
        sm.WorkflowEvent = original_event  # type: ignore[assignment]

    # The contract: nothing got partially persisted. Re-query to verify.
    fresh_app = (
        await db.execute(select(Application).where(Application.id == app_id))
    ).scalars().one()
    assert fresh_app.status == ApplicationState.NEW.value

    rolled_workflow = (
        await db.execute(
            select(Workflow).where(Workflow.application_id == app_id)
        )
    ).scalars().one()
    assert rolled_workflow.current_node == original_workflow_node

    assert (
        await db.execute(
            select(WorkflowEvent).where(WorkflowEvent.application_id == app_id)
        )
    ).scalars().all() == []
    assert (
        await db.execute(
            select(AuditLog).where(AuditLog.application_id == app_id)
        )
    ).scalars().all() == []


# ---------------------------------------------------------------------------
# Old inline test signature (kept for backward compat with `python -m tests.test_state_machine`)
# ---------------------------------------------------------------------------


async def test_transitions():
    """Original inline smoke test — callable via `python -m tests.test_state_machine`."""
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        branch = (await db.execute(select(Branch).limit(1))).scalar_one_or_none()
        if not branch:
            print("[SKIP] No branch in DB; run seed.")
            return

        client = Client(
            branch_id=branch.id,
            business_name="Test Corp",
            applicant_name="Test User",
            mobile_number="9999999999",
            pan_number="ABCDE1234F",
            aadhaar_number_hash="hash",
        )
        db.add(client)
        await db.flush()

        app = Application(
            client_id=client.id,
            branch_id=branch.id,
            application_number=f"TEST-{uuid.uuid4().hex[:8]}",
            status=ApplicationState.NEW.value,
        )
        db.add(app)
        await db.flush()

        try:
            await transition(app, ApplicationState.DOCUMENTS_UPLOADED.value, admin.id if admin else None, db)
            print(f"[OK] Legal Transition Succeeded: {app.status}")
        except Exception as e:
            print(f"[FAIL] Legal Transition Failed: {e}")

        try:
            await transition(app, ApplicationState.READY_FOR_PORTAL.value, admin.id if admin else None, db)
            print("[FAIL] Illegal Transition Succeeded (BAD)")
        except HTTPException as e:
            print(f"[OK] Illegal Transition Caught: {e.detail}")

        await db.rollback()


if __name__ == "__main__":
    asyncio.run(test_transitions())