"""Phase 08 — FastAPI application root.

Wires routers, exception handlers, and the Redis listener lifespan.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.events import (
    EVENTS_CHANNEL,
    clear_after_writes_callbacks,
    on_after_writes,
    publish_event,
)
from app.models.domain import User
from sqlalchemy import select
from app.services.trigger_seeds import run_seeds

# Import API Routers
from app.api.auth import router as auth_router
from app.api.applications import router as apps_router
from app.api.documents import router as docs_router, documents_router
from app.api.workflow import router as workflow_router
from app.api.certificates import router as certificates_router
from app.api.ws import router as ws_router, redis_listener
from app.api.triggers import router as triggers_router
from app.api.webhooks import router as webhooks_router
from app.api.ai_agents import router as ai_agents_router
from app.api.clients import router as clients_router
from app.api.users import router as users_router
from app.api.reports import router as reports_router
from app.api.workflows import router as workflows_router
from app.api.intake import router as intake_router
from app.api.requirement_documents import router as req_docs_router
from app.api.executions import router as executions_router
from app.api.dashboard import router as dashboard_router
from app.api.payments import router as payments_router
from app.api.whatsapp import router as whatsapp_router
from app.api.forms import router as forms_router
from app.api.customers import router as customers_router
from app.api.activity import router as activity_router
from app.api.settings import router as settings_router
from app.api.automation import router as automation_router
from app.api.requirements import router as requirements_router

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: validate config, start Redis listener, clean up on shutdown."""
    settings.validate_for_environment()
    logger.info(
        "Starting AINCURU × TAXLA API in environment=%s",
        settings.ENVIRONMENT,
    )

    async def _publish_via_after_writes(event: dict) -> None:
        await publish_event(event, channel=EVENTS_CHANNEL)

    clear_after_writes_callbacks()
    on_after_writes(_publish_via_after_writes)

    # Seed default triggers (best-effort)
    try:
        async with AsyncSessionLocal() as db:
            sa = (
                await db.execute(
                    select(User).where(User.role == "SUPER_ADMIN").limit(1)
                )
            ).scalars().first()
            super_admin_id = sa.id if sa else None
            await run_seeds(db, super_admin_id=super_admin_id)
    except Exception:
        logger.exception("trigger_seeds.run_seeds failed (non-fatal)")

    listener_task = asyncio.create_task(redis_listener())
    try:
        yield
    finally:
        logger.info("Shutting down: cancelling Redis listener")
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AINCURU × TAXLA Platform API",
    description="Enterprise Automation Platform — MSME / Udyam Registration Engine V1",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Register API Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(apps_router, prefix="/api/v1")
app.include_router(docs_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(workflow_router, prefix="/api/v1")
app.include_router(certificates_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
app.include_router(triggers_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(ai_agents_router, prefix="/api/v1")
app.include_router(clients_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(intake_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(whatsapp_router, prefix="/api/v1")
app.include_router(forms_router, prefix="/api/v1")
app.include_router(customers_router, prefix="/api/v1")
app.include_router(activity_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(automation_router, prefix="/api/v1")
app.include_router(requirements_router, prefix="/api/v1")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = str(uuid.uuid4())
    logger.exception(
        "Unhandled exception [correlation_id=%s] on %s %s",
        correlation_id,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "type": "https://api.taxla.com/errors/INTERNAL_SERVER_ERROR",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An internal error occurred. Please contact support with the correlation id.",
            "instance": request.url.path,
            "correlation_id": correlation_id,
        },
        headers={"X-Correlation-Id": correlation_id},
    )


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "system": "AINCURU x TAXLA API Engine",
        "version": "1.1.0",
        "environment": settings.ENVIRONMENT,
    }