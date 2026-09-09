"""ARQ OCR Worker delegating to WorkflowOrchestrator."""
from __future__ import annotations

import uuid
import logging
from app.core.database import AsyncSessionLocal
from app.services.workflow_orchestrator import WorkflowOrchestrator

logger = logging.getLogger("taxla.worker.ocr")


async def ocr_extraction_job(ctx, application_id_str: str, document_id_str: str):
    """ARQ job: process document through the autonomous intelligence pipeline."""
    app_id = uuid.UUID(application_id_str)
    doc_id = uuid.UUID(document_id_str)

    logger.info("Executing autonomous document pipeline for app=%s doc=%s", app_id, doc_id)
    async with AsyncSessionLocal() as db:
        result = await WorkflowOrchestrator.process_document_pipeline(
            application_id=app_id,
            document_id=doc_id,
            db=db,
        )
        logger.info("Autonomous document pipeline result: %s", result)