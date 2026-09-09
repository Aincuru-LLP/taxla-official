"""Application state machine.

The ``transition()`` function is the single chokepoint for changing an
application's ``status``. Every call writes FOUR rows in the same DB
transaction (caller commits):

  1. ``Application.status`` — the new state.
  2. ``Workflow.current_node`` + ``Workflow.status`` — the workflow row that
     tracks which node the application is currently in. ``status`` is set to
     ``RUNNING`` / ``EXCEPTION`` / ``COMPLETED`` depending on the target.
  3. ``WorkflowEvent`` — one row per transition recording ``node_key``,
     ``event_type`` (ENTERED / COMPLETED / FAILED), ``status``, ``payload``
     (snapshot of from/to), and ``error_code`` if FAILED.
  4. ``AuditLog`` — one row per transition recording the actor + from/to.

Atomicity contract: all four rows are added to the session before the caller
calls ``db.commit()``. If any of them raises, the caller can roll back the
whole transition by not committing.

Recovery model:
  * ``EXCEPTION`` carries an explicit ``resume_target`` (stored in
    ``Workflow.context_json["resume_target"]``).
  * The ONLY legal transition from ``EXCEPTION`` is ``EXCEPTION → resume_target``.
  * Callers MUST pass ``resume_target=...`` when transitioning out of
    ``EXCEPTION``. Anything else raises ``HTTP 409``.

Reviewer decisions (Phase 07):
  * NIC_REVIEW → READY_FOR_PORTAL: APPROVE / OVERRIDE (picks NIC codes).
  * NIC_REVIEW → DATA_VERIFICATION: REJECT (re-classify with new info).
  * VALIDATION_REVIEW → NIC_REVIEW: approve medium-confidence extraction.
  * VALIDATION_REVIEW → HUMAN_REVIEW_REQUIRED: reject (re-upload route).
  * HUMAN_REVIEW → APPROVED: final reviewer signoff.

The historical ``RESUME`` bypass (``RESUME → anything``) has been removed.
``RESOLVED`` and ``RESUME`` remain in the enum for backwards compatibility
but have no legal successors — they are terminal.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import (
    _emit_to_callbacks,
    build_state_transition_event,
)
from app.models.domain import Application, AuditLog, Workflow, WorkflowEvent
from app.models.state import ApplicationState


def _utc_now() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# State transition map
# ---------------------------------------------------------------------------
# Maps every ApplicationState → list of legal next states.
# Per the recovery model, EXCEPTION transitions are NOT in this table; they
# are validated separately inside transition() against the explicit
# resume_target argument.
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: Dict[str, list[str]] = {
    # Happy path
    ApplicationState.NEW.value: [ApplicationState.DOCUMENTS_UPLOADED.value],
    ApplicationState.DOCUMENTS_UPLOADED.value: [ApplicationState.PROCESSING.value],
    ApplicationState.PROCESSING.value: [
        ApplicationState.EXTRACTED.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.EXTRACTED.value: [
        ApplicationState.VALIDATION.value,
        ApplicationState.DUPLICATE_PAN_DETECTED.value,
    ],
    ApplicationState.VALIDATION.value: [
        ApplicationState.NIC_REVIEW.value,                # HIGH confidence (Phase 04)
        ApplicationState.VALIDATION_REVIEW.value,         # MEDIUM confidence (Phase 04)
        ApplicationState.HUMAN_REVIEW_REQUIRED.value,     # LOW confidence (Phase 04)
        ApplicationState.EXCEPTION.value,
        ApplicationState.DUPLICATE_PAN_DETECTED.value,
    ],
    # Phase 04 — reviewer override + operator re-upload paths.
    ApplicationState.VALIDATION_REVIEW.value: [
        ApplicationState.NIC_REVIEW.value,                # reviewer approves
        ApplicationState.HUMAN_REVIEW_REQUIRED.value,     # reviewer rejects
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.HUMAN_REVIEW_REQUIRED.value: [
        ApplicationState.DOCUMENTS_UPLOADED.value,        # operator re-uploads
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.NIC_REVIEW.value: [
        ApplicationState.READY_FOR_PORTAL.value,
        ApplicationState.DATA_VERIFICATION.value,           # Phase 07 — NIC_REJECT: back to data verification
        ApplicationState.EXCEPTION.value,
        ApplicationState.UAM_NOT_FOUND.value,
    ],
    ApplicationState.READY_FOR_PORTAL.value: [
        ApplicationState.PORTAL_RUNNING.value,
        ApplicationState.OTP_REQUIRED.value,
        ApplicationState.EXCEPTION.value,
        ApplicationState.UAM_NOT_FOUND.value,
    ],
    ApplicationState.PORTAL_RUNNING.value: [
        ApplicationState.OTP_REQUIRED.value,
        ApplicationState.OTP_VERIFIED.value,
        ApplicationState.HUMAN_REVIEW.value,
        ApplicationState.SUBMITTING.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.OTP_REQUIRED.value: [
        ApplicationState.OTP_VERIFIED.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.OTP_VERIFIED.value: [
        ApplicationState.PORTAL_RUNNING.value,
        ApplicationState.HUMAN_REVIEW.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.HUMAN_REVIEW.value: [
        ApplicationState.APPROVED.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.APPROVED.value: [
        ApplicationState.SUBMITTING.value,
        ApplicationState.EXCEPTION.value,  # Phase 09 — worker can detect portal-side errors post-approval
    ],
    ApplicationState.SUBMITTING.value: [
        ApplicationState.SUBMITTED.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.SUBMITTED.value: [
        ApplicationState.CERTIFICATE_READY.value,
        ApplicationState.AADHAAR_OTP.value,
        ApplicationState.EXCEPTION.value,
    ],
    # Udyam portal verification chain — added in Phase 03 (per input
    # requirmentsv2.md §39 / §1211-1220 verification flow).
    ApplicationState.AADHAAR_OTP.value: [
        ApplicationState.PAN_VERIFICATION.value,
        ApplicationState.SUBMITTED.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.PAN_VERIFICATION.value: [
        ApplicationState.DATA_VERIFICATION.value,
        ApplicationState.DUPLICATE_PAN_DETECTED.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.DATA_VERIFICATION.value: [
        ApplicationState.REGISTERED.value,
        ApplicationState.DUPLICATE_PAN_DETECTED.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.REGISTERED.value: [
        ApplicationState.CERTIFICATE_READY.value,
        ApplicationState.EXCEPTION.value,
    ],
    ApplicationState.CERTIFICATE_READY.value: [ApplicationState.COMPLETED.value],
    ApplicationState.COMPLETED.value: [],  # terminal
    # Error states — only escape is into EXCEPTION for human review.
    ApplicationState.DUPLICATE_PAN_DETECTED.value: [ApplicationState.EXCEPTION.value],
    ApplicationState.UAM_NOT_FOUND.value: [ApplicationState.EXCEPTION.value],
    # RESOLVED / RESUME retained for backward compatibility; no outgoing
    # transitions (recovery now goes through EXCEPTION → resume_target).
    ApplicationState.RESOLVED.value: [],
    ApplicationState.RESUME.value: [],
    # EXCEPTION is intentionally absent — see transition() body for the
    # resume_target-only validation rule.
}


TERMINAL_STATES: set[str] = {ApplicationState.COMPLETED.value}
"""States that mark the application workflow as finished."""


def _workflow_status_for(new_state: str, error_code: Optional[str]) -> str:
    """Decide what the Workflow.status field should be after this transition."""
    if new_state == ApplicationState.COMPLETED.value:
        return "COMPLETED"
    if new_state == ApplicationState.EXCEPTION.value:
        return "EXCEPTION"
    return "RUNNING"


def _event_type_for(new_state: str, error_code: Optional[str]) -> str:
    """Decide WorkflowEvent.event_type for this transition."""
    if error_code:
        return "FAILED"
    if new_state in TERMINAL_STATES:
        return "COMPLETED"
    return "ENTERED"


async def _get_or_create_workflow(
    db: AsyncSession, application: Application
) -> Workflow:
    """Return the application's Workflow row, creating it if missing.

    Defensive: Workflow should already exist (it's created alongside
    Application in the API). But we don't want a missing workflow to break
    transition() — create a row on demand.

    Always queries the DB rather than trusting the ``Application.workflow``
    relationship. Lazy-loading the relationship in async context without an
    active query raises ``MissingGreenlet``; the explicit query is cheaper
    than tracking the backref state.
    """
    result = await db.execute(
        select(Workflow).where(Workflow.application_id == application.id)
    )
    workflow = result.scalars().first()
    if workflow is None:
        workflow = Workflow(
            application_id=application.id,
            current_node=application.status or ApplicationState.NEW.value,
            status="RUNNING",
            context_json={},
        )
        db.add(workflow)
        await db.flush()
    return workflow


async def transition(
    application: Application,
    new_state: str,
    actor_id: Optional[uuid.UUID],
    db: AsyncSession,
    payload_json: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    resume_target: Optional[str] = None,
) -> Application:
    """Atomically transition an application to ``new_state``.

    Validates legality, then writes Application.status, Workflow row,
    WorkflowEvent, and AuditLog. The caller is responsible for committing
    or rolling back.

    From EXCEPTION: MUST pass ``resume_target`` matching ``new_state``.
    Anything else raises HTTP 409.

    Raises:
        HTTPException 409: illegal transition.
    """
    current_state = application.status

    # --- validation -------------------------------------------------------
    if current_state == ApplicationState.EXCEPTION.value:
        if not resume_target or resume_target != new_state:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=(
                    f"From EXCEPTION, transition must pass resume_target='{new_state}'; "
                    f"got resume_target={resume_target!r}"
                ),
            )
    else:
        allowed = VALID_TRANSITIONS.get(current_state, [])
        if new_state not in allowed:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Illegal state transition from {current_state} to {new_state}",
            )

    # --- writes (all added to session; caller commits) --------------------
    # 1. Application
    application.status = new_state

    # 2. Workflow
    workflow = await _get_or_create_workflow(db, application)
    workflow.current_node = new_state
    workflow.status = _workflow_status_for(new_state, error_code)
    workflow.context_json = workflow.context_json or {}
    if new_state == ApplicationState.EXCEPTION.value and resume_target:
        # Persist the resume target for later recovery.
        workflow.context_json["resume_target"] = resume_target
    workflow.updated_at = _utc_now()

    # 3. WorkflowEvent
    merged_payload = {
        "from_state": current_state,
        "to_state": new_state,
        **(payload_json or {}),
    }
    event = WorkflowEvent(
        workflow_id=workflow.id,
        application_id=application.id,
        node_key=new_state,
        event_type=_event_type_for(new_state, error_code),
        status=new_state,
        payload_json=merged_payload,
        error_code=error_code,
    )
    db.add(event)

    # 4. AuditLog
    audit = AuditLog(
        actor_id=actor_id,
        application_id=application.id,
        action=f"STATE_TRANSITION_{new_state}",
        metadata_json=merged_payload,
    )
    db.add(audit)

    # 5. Notify subscribers (Phase 08 — trigger-action system).
    # The fan-out happens AFTER the writes are added to the session but
    # BEFORE the caller commits. If the caller's commit fails, the
    # subscriber events fire but the DB rolls back — that's acceptable
    # because the audit log + workflow_event row would also be rolled
    # back, and downstream consumers re-derive their view from those
    # rows in any future catch-up worker.
    event = build_state_transition_event(
        application_id=application.id,
        from_state=current_state,
        to_state=new_state,
        payload_json=payload_json,
        branch_id=getattr(application, "branch_id", None),
        actor_id=actor_id,
    )
    await _emit_to_callbacks(event)

    return application
