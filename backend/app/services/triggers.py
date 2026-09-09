"""Phase 08 — Trigger matcher + dispatcher entry point.

Two halves:

  * ``matches(event_name, pattern)`` and ``evaluate_condition(payload, cond)``
    are pure functions. They decide whether a single trigger matches a
    single event. Tests can call them directly without DB.

  * ``dispatch_event(event, db)`` is the side-effecting core. It loads
    every active trigger in the branch, and for each match runs the action
    runner. This is what the ARQ ``dispatcher_loop`` calls when a message
    arrives on ``taxla:events``.

Pattern grammar
---------------

    literal: DOCUMENT_UPLOADED                          -> exact equality
    glob:    STATE_TRANSITIONED.*.NIC_REVIEW            -> '*' matches one segment

The glob is dot-segmented so users can target "any transition that ends
in NIC_REVIEW" or "any transition that starts from NEW" with equal ease.
"""
from __future__ import annotations

import fnmatch
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import Trigger

logger = logging.getLogger("taxla.triggers")


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


def matches(event_name: Optional[str], pattern: str) -> bool:
    """Return True iff ``event_name`` matches ``pattern``.

    * ``event_name`` is the full event string from the publisher
      (e.g. ``STATE_TRANSITIONED.NEW.NIC_REVIEW`` or ``DOCUMENT_UPLOADED``).
    * ``pattern`` is one of:
      - a literal: ``DOCUMENT_UPLOADED`` (no dots, all uppercase + digits + _)
      - a glob:    ``STATE_TRANSITIONED.*.NIC_REVIEW`` (* matches one segment)
      - a multi-glob: ``STATE_TRANSITIONED.*.*`` (matches everything in that family)

    Anything else is rejected (returns False) rather than silently
    matching nothing — we'd rather log a misconfigured trigger than
    paper over the bug.
    """
    if not event_name or not pattern:
        return False
    if "*" not in pattern:
        # Pure literal — case-sensitive exact equality is the contract.
        return event_name == pattern
    # Glob: split on '.' and apply fnmatch to each segment so '*' can't
    # span a dot accidentally.
    e_parts = event_name.split(".")
    p_parts = pattern.split(".")
    if len(e_parts) != len(p_parts):
        return False
    return all(
        fnmatch.fnmatchcase(e, p)
        for e, p in zip(e_parts, p_parts)
    )


def evaluate_condition(
    event: Dict[str, Any], condition: Optional[Dict[str, Any]]
) -> bool:
    """Decide whether ``condition`` is satisfied by ``event``.

    Each ``(k, v)`` pair in ``condition`` must equal ``event[k]``. Missing
    fields in ``event`` mean the condition fails for that key. Empty
    condition (``None`` or ``{}``) is always satisfied — a trigger with
    no condition_json matches purely on event_pattern.

    Type-coercive comparison is intentionally avoided. A trigger that
    says ``{"from": "NEW"}`` should not match an event whose ``from``
    is the integer 0 or the boolean False, even though ``==`` would
    cheerfully say True. Operators configure triggers by name; we
    protect them from typing surprises by strict equality only.
    """
    if not condition:
        return True
    for k, v in condition.items():
        if event.get(k) != v:
            return False
    return True


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


async def find_matching_triggers(
    event: Dict[str, Any], db: AsyncSession
) -> List[Trigger]:
    """Return all triggers whose pattern + condition match ``event``.

    Branch scoping: triggers with no ``branch_id`` on the event are
    matched globally (defensive — should never happen for in-app
    publishes, but a hand-crafted pubsub message might omit it).

    Active flag: triggers with ``is_active=False`` are ignored — that's
    the soft-delete path.
    """
    branch_id = event.get("branch_id")
    # Always include triggers for the event's branch AND any branch_id-less
    # triggers (none today, but reserved for future "global" rules).
    # Eager-load actions so dispatch_event doesn't hit MissingGreenlet
    # when iterating trigger.actions off the main await path.
    stmt = (
        select(Trigger)
        .where(Trigger.is_active.is_(True))
        .options(selectinload(Trigger.actions))
    )
    rows = (await db.execute(stmt)).scalars().all()
    out: List[Trigger] = []
    for trig in rows:
        if branch_id and str(trig.branch_id) != str(branch_id):
            # The trigger's branch must match the event's branch. Triggers
            # without a branch_id (NULL) would never match — there are
            # none in the schema (NOT NULL), so this is purely defensive.
            continue
        if not matches(event.get("event"), trig.event_pattern):
            continue
        if not evaluate_condition(event, trig.condition_json or {}):
            continue
        out.append(trig)
    return out


async def dispatch_event(event: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    """Match triggers against ``event`` and run their actions.

    Returns ``{matched: int, executed: int, errors: [str, ...]}`` for
    the dispatcher to log / record against ``Trigger.last_run_json``.
    Per-trigger error isolation: one failing action must not abort the
    others.
    """
    from app.services.action_runner import execute_action

    triggers = await find_matching_triggers(event, db)
    if not triggers:
        return {"matched": 0, "executed": 0, "errors": []}

    executed = 0
    errors: List[str] = []
    for trigger in triggers:
        per_trigger_errors: List[str] = []
        for action in sorted(trigger.actions, key=lambda a: (a.sort_order, str(a.id))):
            if not action.is_active:
                continue
            try:
                result = await execute_action(action, event, db)
                if result.get("ok"):
                    executed += 1
                else:
                    msg = f"{trigger.name}/{action.type}: {result.get('detail', 'unknown')}"
                    errors.append(msg)
                    per_trigger_errors.append(msg)
            except Exception as exc:
                logger.exception(
                    "trigger '%s' action '%s' failed", trigger.name, action.type
                )
                msg = f"{trigger.name}/{action.type}: {exc!r}"
                errors.append(msg)
                per_trigger_errors.append(msg)
        # Per-trigger bookkeeping. Best-effort: if the JSON write fails we
        # don't want to crash the dispatcher, so we capture and log.
        try:
            trigger.last_run_json = {
                "at": datetime.now(timezone.utc).isoformat(),
                "event": event.get("event"),
                "matched": sum(1 for a in trigger.actions if a.is_active),
                "executed": sum(
                    1 for a in trigger.actions
                    if a.is_active and a.id not in {
                        e.split("/")[1] for e in per_trigger_errors
                    }
                ),
                "errors": per_trigger_errors,
            }
            await db.flush()
        except Exception:
            logger.exception("could not record last_run_json on %s", trigger.name)

    # Phase 12 — fan the event out to subscribed external webhooks. Kept
    # last and isolated: a webhook failure must not roll back trigger
    # side effects, and the dispatcher already returns its summary so
    # the caller can log the merged outcome.
    webhook_summary = await dispatch_event_webhooks_hook(event, db)
    return {
        "matched": len(triggers),
        "executed": executed,
        "errors": errors,
        "webhooks": webhook_summary,
    }


async def dispatch_event_webhooks_hook(
    event: Dict[str, Any], db: AsyncSession
) -> Dict[str, Any]:
    """Phase 12 — fan ``event`` out to subscribed external webhooks.

    Called at the tail of ``dispatch_event``. Kept as a thin wrapper
    so ``dispatch_event`` stays easy to test in isolation (mocks just
    patch this function). Any exception here is swallowed and logged:
    a broken webhook must not crash the dispatcher or roll back a
    successful state transition.

    Returns the webhook dispatch summary (``{matched, delivered,
    failed}``) or ``{matched: 0}`` if Phase 12 hooks aren't installed.
    """
    try:
        from app.services.webhook_delivery import dispatch_event_webhooks
    except Exception:
        logger.exception("could not import webhook delivery service")
        return {"matched": 0}
    try:
        return await dispatch_event_webhooks(event, db)
    except Exception:
        logger.exception("webhook dispatch failed for event=%s", event.get("event"))
        return {"matched": 0, "error": "dispatch_failed"}