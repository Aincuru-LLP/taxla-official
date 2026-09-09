"""Confidence-branched validation engine for extracted application fields.

Phase 04 — replaces the previous stub (which unconditionally transitioned to
NIC_REVIEW). Per ``documents/19_document_processing.md`` the engine now:

  1. Loads every ExtractedData row for the application.
  2. Runs each value through its registered format validator from
     ``app.services.validators`` (PAN, Aadhaar, IFSC, GSTIN, mobile, email, pincode).
     Persists a per-row ``validation_errors`` list — JSON shape
     ``[{validator: <name>, message: <str>}, ...]``.
  3. Sets ``validation_status`` to PASS / FAIL on each row.
  4. Computes the mean ``final_confidence`` across all rows, then branches:

     * **HIGH**   (mean >= 0.85)         -> ``NIC_REVIEW``
     * **MEDIUM** (0.70 <= mean < 0.85)  -> ``VALIDATION_REVIEW``
       (also publishes a notification on the ``taxla:updates`` Redis channel
       so a reviewer sees a toast in the UI)
     * **LOW**    (mean < 0.70)          -> ``HUMAN_REVIEW_REQUIRED``

  5. Transitions via ``transition()`` so the state machine writes the matching
     Workflow + WorkflowEvent + AuditLog atomically.

Validation failures (e.g. malformed PAN) do NOT change the branching: a field
that fails format is not the same as a field that the LLM extracted
uncertainly. Format errors are persisted on the row and surfaced to the
reviewer; the state branch is still driven by mean confidence.
"""
from __future__ import annotations

import json
import logging
import uuid
from statistics import mean
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.state_machine import transition
from app.models.domain import Application, ExtractedData
from app.models.state import ApplicationState
from app.services.validators import VALIDATION_RULES

logger = logging.getLogger(__name__)

# Confidence thresholds per Phase 04 plan section 1.
CONFIDENCE_HIGH_THRESHOLD: float = 0.85
CONFIDENCE_MEDIUM_THRESHOLD: float = 0.70

# Redis pub/sub channel the UI listens on for "validation needs review" toasts.
UI_UPDATE_CHANNEL = "taxla:updates"


def _row_validation_errors(field_name: str, field_value: Optional[str]) -> List[Dict[str, str]]:
    """Run the registered validator for ``field_name`` against ``field_value``.

    Returns an empty list when no validator is registered, when the value is
    blank (whitespace is acceptable as "we don't have it yet"), or when the
    value passes. Otherwise returns a single-entry list describing which
    validator failed and why.
    """
    validator = VALIDATION_RULES.get(field_name)
    if validator is None:
        return []
    if field_value is None or not field_value.strip():
        # Blank values are not "invalid format" — they're "missing". The UI
        # surfaces missing-required separately; here we skip format checking.
        return []
    try:
        ok = validator(field_value)
    except Exception as exc:  # validator raised — treat as a soft failure
        return [{"validator": validator.__name__, "message": f"validator raised: {exc!r}"}]
    if ok:
        return []
    return [
        {
            "validator": validator.__name__,
            "message": f"value '{field_value}' failed format check for {field_name}",
        }
    ]


def _classify_confidence(mean_confidence: float) -> str:
    """Map a 0-1 confidence score to one of HIGH / MEDIUM / LOW."""
    if mean_confidence >= CONFIDENCE_HIGH_THRESHOLD:
        return "HIGH"
    if mean_confidence >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


async def _publish_review_notification(application_id: uuid.UUID, mean_confidence: float) -> None:
    """Publish a toast notification on the Redis UI channel.

    Best-effort: a Redis outage must NOT fail the validation pipeline (the
    transition has already been committed). Errors are logged and swallowed.
    """
    payload = {
        "type": "VALIDATION_REVIEW_REQUIRED",
        "application_id": str(application_id),
        "mean_confidence": mean_confidence,
        "message": "Application needs validation review (MEDIUM confidence)",
    }
    try:
        client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
        await client.publish(UI_UPDATE_CHANNEL, json.dumps(payload))
        await client.aclose()
    except Exception as exc:
        logger.warning(
            "Failed to publish VALIDATION_REVIEW_REQUIRED notification to %s: %r",
            UI_UPDATE_CHANNEL,
            exc,
        )


class ValidationEngine:
    """Per-application confidence-branched validation pass."""

    @staticmethod
    async def validate_application_extractions(
        application_id: uuid.UUID,
        db: AsyncSession,
        *,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Optional[str]:
        """Run the full Phase 04 validation pass for one application.

        Returns:
            None on success (whether branched HIGH/MEDIUM/LOW).
            A short error code string if the application could not be found.

        Side effects:
            * Updates each ExtractedData.validation_status / validation_errors.
            * Transitions Application.status to NIC_REVIEW / VALIDATION_REVIEW /
              HUMAN_REVIEW_REQUIRED based on mean confidence.
            * Publishes to ``taxla:updates`` Redis channel on the MEDIUM path.
        """
        # 1. Load the application.
        app_row = (
            await db.execute(select(Application).where(Application.id == application_id))
        ).scalars().first()
        if not app_row:
            return "APP_NOT_FOUND"

        # 2. Load every ExtractedData row.
        extractions = (
            await db.execute(
                select(ExtractedData).where(ExtractedData.application_id == application_id)
            )
        ).scalars().all()

        # 3. Move into VALIDATION if not already there.
        if app_row.status != ApplicationState.VALIDATION.value:
            try:
                if app_row.status == ApplicationState.NEW.value:
                    await transition(app_row, ApplicationState.DOCUMENTS_UPLOADED.value, actor_id, db)
                if app_row.status == ApplicationState.DOCUMENTS_UPLOADED.value:
                    await transition(app_row, ApplicationState.PROCESSING.value, actor_id, db)
                if app_row.status == ApplicationState.PROCESSING.value:
                    await transition(app_row, ApplicationState.EXTRACTED.value, actor_id, db)
                if app_row.status == ApplicationState.EXTRACTED.value:
                    await transition(app_row, ApplicationState.VALIDATION.value, actor_id, db)
            except Exception as e:
                logger.warning("Validation transition into VALIDATION: %s", e)

        # 4. Run validators per row + persist per-row validation_errors.
        confidences: List[float] = []
        for ext in extractions:
            errors = _row_validation_errors(ext.field_name, ext.field_value)
            ext.validation_errors = errors
            ext.validation_status = "FAIL" if errors else "PASS"

            chosen = (
                ext.final_confidence
                if ext.final_confidence is not None
                else ext.extraction_confidence
                if ext.extraction_confidence is not None
                else ext.confidence
                if ext.confidence is not None
                else 0.0
            )
            confidences.append(float(chosen))

        # 5. Compute mean confidence across all rows (or 0.0 when nothing extracted).
        mean_confidence = mean(confidences) if confidences else 0.0
        branch = _classify_confidence(mean_confidence)

        # 6. Branch on the classification and transition.
        try:
            if branch == "HIGH":
                if app_row.status == ApplicationState.VALIDATION.value:
                    await transition(
                        app_row,
                        ApplicationState.NIC_REVIEW.value,
                        actor_id,
                        db,
                        payload_json={"mean_confidence": mean_confidence, "branch": branch},
                    )
            elif branch == "MEDIUM":
                if app_row.status == ApplicationState.VALIDATION.value:
                    await transition(
                        app_row,
                        ApplicationState.VALIDATION_REVIEW.value,
                        actor_id,
                        db,
                        payload_json={"mean_confidence": mean_confidence, "branch": branch},
                    )
                await _publish_review_notification(application_id, mean_confidence)
            else:  # LOW
                if app_row.status == ApplicationState.VALIDATION.value:
                    await transition(
                        app_row,
                        ApplicationState.HUMAN_REVIEW_REQUIRED.value,
                        actor_id,
                        db,
                        payload_json={"mean_confidence": mean_confidence, "branch": branch},
                    )
        except Exception as e:
            logger.warning("Validation post-branch transition: %s", e)

        await db.commit()
        return None

    @staticmethod
    async def override_validation_review(
        application_id: uuid.UUID,
        *,
        approve: bool,
        actor_id: uuid.UUID,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """REVIEWER override on the MEDIUM path.

        Called by the PATCH /validation-review endpoint when a reviewer either:

          * **approves** the MEDIUM-confidence extraction -> NIC_REVIEW, or
          * **rejects** it -> HUMAN_REVIEW_REQUIRED (forcing re-upload).

        Returns a small status dict; the endpoint raises HTTPException on
        illegal calls (handled by ``transition()``).
        """
        app_row = (
            await db.execute(select(Application).where(Application.id == application_id))
        ).scalars().first()
        if app_row is None:
            return {"ok": False, "reason": "APP_NOT_FOUND"}

        target = (
            ApplicationState.NIC_REVIEW.value
            if approve
            else ApplicationState.HUMAN_REVIEW_REQUIRED.value
        )
        await transition(
            app_row,
            target,
            actor_id,
            db,
            payload_json={"override": "REVIEWER", "decision": "approve" if approve else "reject"},
        )
        await db.commit()
        return {"ok": True, "new_state": target}