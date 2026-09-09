import asyncio
import json
import logging
from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings

logger = logging.getLogger("taxla.worker")


async def start_playwright_automation_job(ctx, payload_or_id: str | dict, snapshot: dict | None = None):
    """
    Background job to run the Playwright automation script against the target Udyam portal using an approved snapshot.
    """
    from worker.playwright_agent import run_automation
    if isinstance(payload_or_id, dict):
        app_id_str = str(payload_or_id.get("application_id"))
        snap = payload_or_id.get("snapshot") or snapshot
        job_id = payload_or_id.get("automation_job_id")
        await run_automation(app_id_str, snapshot=snap, automation_job_id=job_id)
    else:
        await run_automation(str(payload_or_id), snapshot=snapshot)


from worker.ocr_worker import ocr_extraction_job


# ---------------------------------------------------------------------------
# Phase 08 — Trigger-Action dispatcher
# ---------------------------------------------------------------------------
# ARQ starts the worker with a long-lived ``ctx``. We use that as the
# place to stash a Redis pub/sub connection and a task that fans every
# incoming message into ``dispatch_event``.
# ---------------------------------------------------------------------------

EVENTS_CHANNEL = "taxla:events"


async def dispatcher_loop(ctx):
    """Subscribe to ``taxla:events`` and dispatch each message.

    Per-message error isolation: a failing dispatch should not stop the
    loop. We log + drop and keep going.
    """
    # Reuse ARQ's connection pool rather than opening a new Redis client.
    redis = ctx["redis"]
    pubsub = redis.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    logger.info("dispatcher_loop subscribed to %s", EVENTS_CHANNEL)
    try:
        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue
            try:
                event = json.loads(msg["data"])
            except (TypeError, ValueError):
                logger.exception("dispatcher_loop: bad payload, dropping")
                continue
            try:
                from app.core.database import AsyncSessionLocal
                from app.services.triggers import dispatch_event

                async with AsyncSessionLocal() as db:
                    await dispatch_event(event, db)
                    await db.commit()
            except Exception:
                logger.exception("dispatcher_loop: dispatch failed for %s", event.get("event"))
    finally:
        try:
            await pubsub.unsubscribe(EVENTS_CHANNEL)
        except Exception:
            logger.exception("dispatcher_loop: unsubscribe failed")


async def _on_startup(ctx):
    """ARQ on_startup hook: spawn dispatcher loop in background without blocking worker polling."""
    ctx["dispatcher_task"] = asyncio.create_task(dispatcher_loop(ctx))


async def _cancel_dispatcher(ctx):
    """ARQ on_shutdown hook: cancel the background dispatcher task."""
    task = ctx.get("dispatcher_task")
    if task:
        task.cancel()
    return None


# ARQ Worker Settings
class WorkerSettings:
    redis_settings = RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    functions = [start_playwright_automation_job, ocr_extraction_job]
    on_startup = _on_startup
    on_shutdown = _cancel_dispatcher