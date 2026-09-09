"""Phase 08 — Action runner.

One ``execute_action(action, event, db)`` call dispatches based on
``action.type`` and returns a small dict ``{ok: bool, detail: str}``
that the dispatcher records into ``Trigger.last_run_json``.

Action types
------------

* ``HTTP_WEBHOOK``  — POST ``config_json["url"]`` with the event as
  JSON body. Optional HMAC signature if ``config_json["hmac_secret"]``
  is set. Single attempt, 10-second timeout. Non-2xx => ok=False, drop.
* ``EMAIL``         — insert a row in ``email_outbox`` with
  ``to_address`` / interpolated subject / interpolated body.
  ``${event_field}`` style placeholders are substituted; unknown
  fields become empty strings (so a broken template never crashes the
  dispatcher).
* ``SHELL``         — gated behind ``trigger.created_by.role == "SUPER_ADMIN"``.
  Otherwise logged and skipped. The MVP does not actually exec — that's
  a Phase 12 hardening concern.
* ``STATE_TRANSITION`` — load the Application, call
  ``state_machine.transition(application, config_json["to_state"], None, db)``.
  The new transition re-emits its own event via the after_writes hook,
  chaining naturally.
* ``PLAYWRIGHT``    — enqueue the existing
  ``start_playwright_automation_job`` via ARQ, passing the event's
  ``application_id``. No-op if Redis is unreachable.

Each branch returns ``{ok, detail}``. Any unhandled exception inside a
branch is caught and reported as ``{ok: False, detail: repr(exc)}`` so
the dispatcher can keep going.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Any, Dict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.domain import Action, Application, EmailOutbox, Trigger

logger = logging.getLogger("taxla.actions")


# ---------------------------------------------------------------------------
# Config interpolation
# ---------------------------------------------------------------------------
# Templates use ${field} where field is a key in the event dict (or
# ``payload`` for nested fields). The matcher is intentionally
# permissive — an unknown placeholder becomes "" rather than raising, so
# a half-broken email template doesn't take down the whole dispatcher.
_PLACEHOLDER = re.compile(r"\$\{([a-zA-Z0-9_.]+)\}")


def _render_template(template: str, event: Dict[str, Any]) -> str:
    def _lookup(name: str) -> str:
        cur: Any = event
        for part in name.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return ""
            if cur is None:
                return ""
        return str(cur)

    return _PLACEHOLDER.sub(lambda m: _lookup(m.group(1)), template)


# ---------------------------------------------------------------------------
# Per-type runners
# ---------------------------------------------------------------------------


async def _run_http_webhook(
    action: Action, event: Dict[str, Any]
) -> Dict[str, Any]:
    url = (action.config_json or {}).get("url")
    if not url:
        return {"ok": False, "detail": "HTTP_WEBHOOK missing 'url'"}
    secret = (action.config_json or {}).get("hmac_secret")
    body = json.dumps(event, default=str).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret:
        sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-Signature"] = f"sha256={sig}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        # MVP decision: log + drop. Phase 12 will add retry with backoff.
        return {"ok": False, "detail": f"network error: {exc!r}"}
    if 200 <= resp.status_code < 300:
        return {"ok": True, "detail": f"{resp.status_code}"}
    return {"ok": False, "detail": f"status={resp.status_code}"}


async def _run_email(
    action: Action, event: Dict[str, Any], db: AsyncSession
) -> Dict[str, Any]:
    cfg = action.config_json or {}
    to = cfg.get("to")
    subject_tpl = cfg.get("subject", "(no subject)")
    body_tpl = cfg.get("body", "")
    if not to:
        return {"ok": False, "detail": "EMAIL missing 'to'"}
    related_app_id = None
    if event.get("application_id"):
        try:
            related_app_id = uuid.UUID(event["application_id"])
        except (TypeError, ValueError):
            related_app_id = None
    outbox = EmailOutbox(
        to_address=to,
        subject=_render_template(subject_tpl, event)[:998],
        body=_render_template(body_tpl, event),
        status="queued",
        related_application_id=related_app_id,
        related_trigger_id=action.trigger_id,
    )
    db.add(outbox)
    await db.flush()
    return {"ok": True, "detail": f"queued email to {to} (id={outbox.id})"}


async def _run_shell(
    action: Action, event: Dict[str, Any], db: AsyncSession, trigger: Trigger
) -> Dict[str, Any]:
    # MVP: gate on role. We don't actually exec — operators can wire
    # something safer in Phase 12 if they really need shell hooks.
    if not trigger or not trigger.creator or trigger.creator.role != "SUPER_ADMIN":
        return {
            "ok": False,
            "detail": "SHELL actions require SUPER_ADMIN creator",
        }
    cmd = (action.config_json or {}).get("command")
    if not cmd:
        return {"ok": False, "detail": "SHELL missing 'command'"}
    logger.warning(
        "SHELL action on trigger '%s' accepted but not executed (MVP gate)",
        trigger.name,
    )
    return {"ok": True, "detail": "SHELL accepted (no-op in MVP)"}


async def _run_state_transition(
    action: Action, event: Dict[str, Any], db: AsyncSession
) -> Dict[str, Any]:
    cfg = action.config_json or {}
    to_state = cfg.get("to_state")
    if not to_state:
        return {"ok": False, "detail": "STATE_TRANSITION missing 'to_state'"}
    app_id_str = event.get("application_id")
    if not app_id_str:
        return {"ok": False, "detail": "STATE_TRANSITION event missing application_id"}
    try:
        app_uuid = uuid.UUID(app_id_str)
    except (TypeError, ValueError):
        return {"ok": False, "detail": f"bad application_id: {app_id_str!r}"}

    # Lazy-load Application. Caller's session is async so we use SELECT.
    app_row = (await db.execute(
        select(Application).where(Application.id == app_uuid)
    )).scalars().first()
    if not app_row:
        return {"ok": False, "detail": f"application {app_id_str} not found"}

    # If the app is already in to_state, the state machine will 409.
    # Treat that as a no-op success — chained triggers shouldn't blow
    # up the dispatcher when an event happens to fire twice.
    if app_row.status == to_state:
        return {
            "ok": True,
            "detail": f"already in {to_state}, no-op",
        }

    # Import lazily so the action runner doesn't pull the state machine
    # at module load time (the state machine imports this module's
    # callers — and we want to avoid the cycle).
    from app.core.state_machine import transition

    try:
        await transition(
            app_row,
            to_state,
            # No actor — this came from the dispatcher, not a user request.
            # AuditLog.actor_id is nullable, so this is honest.
            actor_id=None,
            db=db,
            payload_json={
                "triggered_by": str(action.trigger_id),
                "via_event": event.get("event"),
            },
        )
    except Exception as exc:
        # transition() raises HTTPException on illegal transitions. We
        # catch broadly and report.
        return {"ok": False, "detail": f"transition failed: {exc!r}"}
    return {"ok": True, "detail": f"transitioned to {to_state}"}


async def _run_playwright(
    action: Action, event: Dict[str, Any]
) -> Dict[str, Any]:
    app_id = event.get("application_id")
    if not app_id:
        return {"ok": False, "detail": "PLAYWRIGHT event missing application_id"}
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        redis_pool = await create_pool(
            RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        )
        try:
            job = await redis_pool.enqueue_job(
                "start_playwright_automation_job", str(app_id)
            )
        finally:
            await redis_pool.aclose()
    except Exception as exc:
        return {"ok": False, "detail": f"ARQ enqueue failed: {exc!r}"}
    job_id = getattr(job, "job_id", None) if job else None
    return {"ok": True, "detail": f"enqueued playwright job {job_id}"}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


async def execute_action(
    action: Action, event: Dict[str, Any], db: AsyncSession
) -> Dict[str, Any]:
    """Run one action and return ``{ok: bool, detail: str}``."""
    # ``action.trigger`` may or may not be loaded depending on whether the
    # caller used selectinload. Try the relationship; fall back to a
    # fresh query if needed (SHELL is the only branch that needs it).
    trigger = action.trigger
    if trigger is None and action.trigger_id is not None:
        trigger = (await db.execute(
            select(Trigger).where(Trigger.id == action.trigger_id)
        )).scalars().first()

    try:
        if action.type == "HTTP_WEBHOOK":
            return await _run_http_webhook(action, event)
        if action.type == "EMAIL":
            return await _run_email(action, event, db)
        if action.type == "SHELL":
            return await _run_shell(action, event, db, trigger)
        if action.type == "STATE_TRANSITION":
            return await _run_state_transition(action, event, db)
        if action.type == "PLAYWRIGHT":
            return await _run_playwright(action, event)
        return {"ok": False, "detail": f"unknown action type {action.type!r}"}
    except Exception as exc:
        logger.exception("action %s failed", action.type)
        return {"ok": False, "detail": repr(exc)}