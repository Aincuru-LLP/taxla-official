"""Event publishing helpers.

The trigger-action system subscribes to a single Redis pub/sub channel
(``taxla:events``) and reacts to whatever lands there. This module owns:

  * the channel name,
  * the ``publish_event`` helper that endpoints call after their DB
    transaction commits,
  * the ``on_after_writes`` registry that the state machine uses to fan
    out events without coupling to Redis at import time.

Design notes
------------

* The state machine (``app/core/state_machine.py``) is purely synchronous
  in shape — it doesn't import Redis. It registers a callback via
  ``on_after_writes`` and the FastAPI lifespan installs the publisher.
  Tests can swap the callback for a no-op or a spy.

* ``publish_event`` is best-effort. If Redis is unreachable we log and
  swallow; the caller has already committed the DB write, and crashing
  the request because the pub/sub bus is down would be worse than
  losing the side-effect. Real recovery is via the
  ``workflow_events`` + ``audit_logs`` rows that the state machine
  already writes — a future catch-up worker can replay them.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("taxla.events")

# Single pub/sub channel. The state machine publishes
# ``STATE_TRANSITIONED`` events; documents.py publishes
# ``DOCUMENT_UPLOADED``. Anything else that wants to react via triggers
# publishes to the same channel.
EVENTS_CHANNEL = "taxla:events"


# ---------------------------------------------------------------------------
# After-writes callback registry
# ---------------------------------------------------------------------------
# Used by state_machine.transition() to notify listeners after a successful
# writes phase, BEFORE the caller commits. The default callback (registered
# in main.py lifespan) publishes to Redis.
# ---------------------------------------------------------------------------

_after_writes_callbacks: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []


def on_after_writes(callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
    """Register an async callback to receive every event after writes."""
    _after_writes_callbacks.append(callback)


def clear_after_writes_callbacks() -> None:
    """Test helper: drop all registered callbacks."""
    _after_writes_callbacks.clear()


async def _emit_to_callbacks(event: Dict[str, Any]) -> None:
    """Fan an event out to every registered callback.

    Errors in individual callbacks are logged but never raised — one
    misbehaving callback must not abort the others. The state machine
    will already have written the DB rows by the time we get here.
    """
    for cb in _after_writes_callbacks:
        try:
            await cb(event)
        except Exception:
            logger.exception("after_writes callback %r failed", cb)


# ---------------------------------------------------------------------------
# Redis publisher
# ---------------------------------------------------------------------------


async def publish_event(event: Dict[str, Any], *, channel: str = EVENTS_CHANNEL) -> None:
    """Publish a JSON-encoded event to ``channel``.

    Returns silently on failure; logs at WARNING. Callers have already
    committed the DB write, so raising here would just create 500s for
    users when Redis is briefly down.
    """
    payload = dict(event)
    payload.setdefault("event_id", str(uuid.uuid4()))
    payload.setdefault("published_at", datetime.now(timezone.utc).isoformat())
    try:
        client = aioredis.from_url(settings.REDIS_URL)
        try:
            await client.publish(channel, json.dumps(payload, default=str))
        finally:
            await client.aclose()
    except Exception as exc:
        logger.warning("publish_event(%s) dropped: %s", payload.get("event"), exc)


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------


def build_state_transition_event(
    *,
    application_id: uuid.UUID,
    from_state: str,
    to_state: str,
    payload_json: Dict[str, Any] | None,
    branch_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
) -> Dict[str, Any]:
    """Compose the standard event dict for a state transition.

    The event name is ``STATE_TRANSITIONED.{from}.{to}`` so glob
    patterns can match by destination (``STATE_TRANSITIONED.*.NIC_REVIEW``)
    or by origin (``STATE_TRANSITIONED.NEW.*``).
    """
    return {
        "event": f"STATE_TRANSITIONED.{from_state}.{to_state}",
        "application_id": str(application_id),
        "from": from_state,
        "to": to_state,
        "branch_id": str(branch_id) if branch_id else None,
        "actor_id": str(actor_id) if actor_id else None,
        "payload": payload_json or {},
    }