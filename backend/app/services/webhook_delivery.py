"""Phase 12 — Outbound webhook delivery.

One job per ``(webhook, event)``: POST the event JSON to ``webhook.url``,
sign with HMAC-SHA256, record the attempt, retry on non-2xx.

Why a sidecar module:
  * ``services/triggers.py`` is the dispatcher's hot path — adding httpx
    + retry state machine to it makes the test surface huge. Keeping
    the delivery loop here means trigger tests stay trivial and the
    retry semantics have exactly one home.
  * Receivers have no shared secret with the backend. The signature
    header is the only thing that lets a receiver prove the call came
    from us, so it has to be correct on every attempt.

Retry policy (from the Phase 12 spec):
  * Backoff: 60s, 300s, 1800s, 7200s between attempts.
  * Max attempts: 4. After that we mark ``webhook.last_error`` and
    stop — the operator has to manually retry by toggling
    ``is_active`` or fixing the URL.
  * Retries happen via inline ``asyncio.sleep`` between attempts; the
    caller is an ARQ worker so blocking the slot is acceptable and
    simpler than chaining deferred jobs.

Testability:
  * ``transport`` kwarg accepts an ``httpx.MockTransport`` so tests
    can drive 2xx / 5xx / network error without binding a port.
  * ``sleep_fn`` kwarg accepts a callable so tests can skip the
    backoff windows in milliseconds.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Webhook, WebhookDelivery

logger = logging.getLogger("taxla.webhooks")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Phase 12 spec: retry on failure at 1m, 5m, 30m, 2h. Max 4 attempts.
RETRY_DELAYS_SECONDS: List[int] = [60, 300, 1800, 7200]
MAX_ATTEMPTS = 4
DELIVERY_TIMEOUT_SECONDS = 10.0

# Allows tests to override the network call and the wait between retries.
SleepFn = Callable[[float], Awaitable[None]]


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


def sign_payload(secret: str, body: bytes) -> str:
    """Return ``sha256=<hex>`` for the given body using ``secret``.

    Receivers verify by recomputing HMAC-SHA256(secret, raw_body) and
    constant-time comparing. We use ``hmac.compare_digest``-friendly
    hex digest (lowercase, fixed width).
    """
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


# ---------------------------------------------------------------------------
# One attempt
# ---------------------------------------------------------------------------


async def deliver_once(
    webhook: Webhook,
    event: Dict[str, Any],
    attempt: int,
    db: AsyncSession,
    *,
    transport: Optional[httpx.MockTransport] = None,
    sleep_fn: Optional[SleepFn] = None,
) -> WebhookDelivery:
    """POST the event to ``webhook.url`` exactly once and persist the row.

    Returns the ``WebhookDelivery`` row that was written. Caller decides
    what to do next (mark failed, schedule retry, etc).
    """
    sleep_fn = sleep_fn or asyncio.sleep

    event_id_str = event.get("event_id") or str(uuid4())
    event_name = event.get("event") or event.get("event_name") or "unknown"

    body = json.dumps(
        {
            "id": event_id_str,
            "event": event_name,
            "occurred_at": event.get("occurred_at")
            or datetime.now(timezone.utc).isoformat(),
            "branch_id": event.get("branch_id"),
            "application_id": event.get("application_id"),
            "from_state": event.get("from"),
            "to_state": event.get("to"),
            "payload": event.get("payload") or {},
        },
        default=str,
    ).encode("utf-8")

    timestamp = str(int(time.time()))
    signature = sign_payload(webhook.secret, body)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Taxla-Webhooks/1.0",
        "X-Taxla-Event": event_name,
        "X-Taxla-Delivery": event_id_str,
        "X-Taxla-Timestamp": timestamp,
        "X-Taxla-Signature": signature,
    }

    status_code: Optional[int] = None
    response_text: Optional[str] = None
    error_text: Optional[str] = None
    ok = False

    client_kwargs: Dict[str, Any] = {"timeout": DELIVERY_TIMEOUT_SECONDS}
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(webhook.url, content=body, headers=headers)
            status_code = resp.status_code
            # Cap stored body — a hostile receiver can return megabytes.
            response_text = resp.text[:8192] if resp.text else None
            ok = 200 <= resp.status_code < 300
    except httpx.HTTPError as exc:
        ok = False
        error_text = f"{type(exc).__name__}: {exc}"

    delivery = WebhookDelivery(
        webhook_id=webhook.id,
        event_id=UUID(event_id_str) if _looks_like_uuid(event_id_str) else None,
        event_name=event_name,
        attempt_number=attempt,
        status_code=status_code,
        response_body=response_text,
        error=error_text,
    )
    db.add(delivery)

    # Update the parent row's bookkeeping so the UI can show "this
    # webhook looks dead" without scanning the deliveries log.
    webhook.last_triggered_at = datetime.now(timezone.utc)
    webhook.last_status = status_code
    webhook.last_error = error_text or (None if ok else f"status={status_code}")

    await db.flush()
    return delivery


def _looks_like_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Match + dispatch loop
# ---------------------------------------------------------------------------


def _matches_any(event_name: Optional[str], patterns: List[str]) -> bool:
    """Return True if ``event_name`` matches any pattern in ``patterns``.

    Empty list = subscribe to everything (the contract documented on
    the model). A single ``"*"`` also matches everything (handy for
    ops). Otherwise we defer to the same fnmatch-segmented matcher
    triggers use, so webhooks and triggers share semantics.
    """
    if not patterns:
        return True
    if not event_name:
        return False
    import fnmatch

    for pat in patterns:
        if pat == "*":
            return True
        if "*" not in pat:
            if event_name == pat:
                return True
            continue
        e_parts = event_name.split(".")
        p_parts = pat.split(".")
        if len(e_parts) != len(p_parts):
            continue
        if all(fnmatch.fnmatchcase(e, p) for e, p in zip(e_parts, p_parts)):
            return True
    return False


async def _find_matching_webhooks(
    event: Dict[str, Any], db: AsyncSession
) -> List[Webhook]:
    """Return active webhooks in the event's branch whose patterns match."""
    branch_id = event.get("branch_id")
    if not branch_id:
        return []
    try:
        branch_uuid = UUID(str(branch_id))
    except (TypeError, ValueError):
        return []
    stmt = select(Webhook).where(
        Webhook.branch_id == branch_uuid,
        Webhook.is_active.is_(True),
    )
    rows = (await db.execute(stmt)).scalars().all()
    event_name = event.get("event")
    return [w for w in rows if _matches_any(event_name, w.subscribed_events or [])]


async def dispatch_event_webhooks(
    event: Dict[str, Any],
    db: AsyncSession,
    *,
    transport: Optional[httpx.MockTransport] = None,
    sleep_fn: Optional[SleepFn] = None,
) -> Dict[str, Any]:
    """Fan ``event`` out to every matching webhook, with retries.

    Each ``(webhook, event)`` runs ``deliver_once`` up to ``MAX_ATTEMPTS``
    times. Retries use ``RETRY_DELAYS_SECONDS`` between attempts and
    sleep inline (the dispatcher is already inside an ARQ worker, so
    blocking the slot is fine and simpler than scheduling a chain of
    deferred jobs).

    Returns ``{matched: int, delivered: int, failed: int}``.
    """
    sleep_fn = sleep_fn or asyncio.sleep
    webhooks = await _find_matching_webhooks(event, db)
    if not webhooks:
        return {"matched": 0, "delivered": 0, "failed": 0}

    delivered = 0
    failed = 0
    for webhook in webhooks:
        ok = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            row = await deliver_once(
                webhook,
                event,
                attempt,
                db,
                transport=transport,
                sleep_fn=sleep_fn,
            )
            if 200 <= (row.status_code or 0) < 300:
                ok = True
                break
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_DELAYS_SECONDS[attempt - 1]
                logger.info(
                    "webhook %s attempt %d failed (status=%s); retrying in %ds",
                    webhook.id,
                    attempt,
                    row.status_code,
                    delay,
                )
                await sleep_fn(delay)
        if ok:
            delivered += 1
        else:
            failed += 1

    return {"matched": len(webhooks), "delivered": delivered, "failed": failed}