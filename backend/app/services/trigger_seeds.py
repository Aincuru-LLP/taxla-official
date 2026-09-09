"""Phase 08 — Default trigger seeds.

``run_seeds`` is invoked from the FastAPI lifespan. It is idempotent:
re-running it on a branch that already has these triggers is a no-op.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Action, Branch, Trigger

logger = logging.getLogger("taxla.seeds")


# ---------------------------------------------------------------------------
# Seed definitions
# ---------------------------------------------------------------------------
# Each seed is keyed by name. We match on ``(branch_id, name)`` to keep
# things scoped per branch. The email addresses are placeholders —
# operators should swap them for real recipients via the automations UI.

_SEEDS: list[dict] = [
    {
        "name": "seed-ocr-pipeline",
        "event_pattern": "DOCUMENT_UPLOADED",
        "condition_json": {},
        "actions": [
            {
                "type": "STATE_TRANSITION",
                "config_json": {"to_state": "PROCESSING"},
                "sort_order": 0,
            },
        ],
    },
    {
        "name": "seed-notify-reviewers",
        "event_pattern": "STATE_TRANSITIONED.*.NIC_REVIEW",
        "condition_json": {},
        "actions": [
            {
                "type": "EMAIL",
                "config_json": {
                    "to": "reviewers@branch.local",
                    "subject": "Application ${application_id} needs NIC review",
                    "body": "An application has entered NIC_REVIEW.\n\n"
                            "Application ID: ${application_id}\n"
                            "Branch ID: ${branch_id}",
                },
                "sort_order": 0,
            },
        ],
    },
    {
        "name": "seed-notify-operator-otp",
        "event_pattern": "STATE_TRANSITIONED.*.OTP_REQUIRED",
        "condition_json": {},
        "actions": [
            {
                "type": "EMAIL",
                "config_json": {
                    "to": "operator@branch.local",
                    "subject": "Application ${application_id} needs OTP",
                    "body": "An application needs OTP entry.\n\n"
                            "Application ID: ${application_id}\n"
                            "Branch ID: ${branch_id}",
                },
                "sort_order": 0,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def _first_branch(db: AsyncSession) -> Optional[Branch]:
    return (await db.execute(select(Branch).order_by(Branch.created_at.asc()).limit(1))).scalars().first()


async def run_seeds(
    db: AsyncSession, super_admin_id: Optional[uuid.UUID]
) -> int:
    """Insert the default triggers if absent.

    Returns the count of newly inserted triggers. Errors during the seed
    pass are logged but never raised — the lifespan should not crash
    just because seeding failed.
    """
    branch = await _first_branch(db)
    if branch is None:
        logger.info("trigger_seeds: no branches found, skipping")
        return 0

    creator_id = super_admin_id or uuid.uuid4()  # placeholder OK if no super admin

    inserted = 0
    for spec in _SEEDS:
        existing = (await db.execute(
            select(Trigger).where(
                Trigger.branch_id == branch.id,
                Trigger.name == spec["name"],
            )
        )).scalars().first()
        if existing is not None:
            continue
        trigger = Trigger(
            branch_id=branch.id,
            name=spec["name"],
            event_pattern=spec["event_pattern"],
            condition_json=spec.get("condition_json") or {},
            is_active=True,
            created_by=creator_id,
        )
        for a in spec["actions"]:
            trigger.actions.append(
                Action(
                    type=a["type"],
                    config_json=a.get("config_json") or {},
                    sort_order=a.get("sort_order", 0),
                    is_active=True,
                )
            )
        db.add(trigger)
        inserted += 1

    if inserted:
        await db.commit()
        logger.info("trigger_seeds: inserted %d trigger(s) on branch %s", inserted, branch.id)
    else:
        logger.debug("trigger_seeds: nothing to insert (idempotent)")
    return inserted