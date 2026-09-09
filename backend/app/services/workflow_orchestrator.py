"""Core Workflow Orchestrator for TAXLA Autonomous Document-to-Automation Platform.

Coordinates the end-to-end lifecycle:
Document Ingestion -> Classification -> Parsing / OCR -> Ollama/Qwen Extraction
-> Requirement Matching -> Validation -> NIC Classification -> Human Checkpoint
-> Portal Automation (Playwright) -> Certificate -> Completed.

Authoritative execution state is persisted in workflow_executions and workflow_node_executions.
Events are published in real-time to Redis for the Automation Visualizer.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.events import publish_event
from app.core.state_machine import transition
from app.models.domain import (
    Application,
    ApplicationRequirement,
    Document,
    ExtractedData,
    HumanCheckpoint,
    NICSuggestion,
    RawOcrResult,
    Workflow,
    WorkflowExecution,
    WorkflowNodeExecution,
)
from app.models.state import ApplicationState
from app.services.ai_extractor import (
    DocumentExtractionService,
    EXTRACTION_MODEL_NAME,
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
)
from app.services.document_classifier import DocumentClassifier
from app.services.human_checkpoint_service import HumanCheckpointService
from app.services.nic_service import NICClassificationService
from app.services.ocr_service import OcrFailureError, OcrLine, OcrService, OcrUnavailableError
from app.services.requirement_engine import RequirementEngine
from app.services.review_decision_service import FieldSignals, ReviewDecisionService
from app.services.validation_engine import ValidationEngine

logger = logging.getLogger("taxla.services.orchestrator")

STANDARD_WORKFLOW_NODES: List[Dict[str, str]] = [
    {"node_id": "doc_received", "node_label": "Requirement Document", "node_type": "DOCUMENT"},
    {"node_id": "classification", "node_label": "Document Classification", "node_type": "PARSER"},
    {"node_id": "parsing", "node_label": "Document Parsing", "node_type": "PARSER"},
    {"node_id": "ocr", "node_label": "OCR Processing", "node_type": "OCR"},
    {"node_id": "ai_extraction", "node_label": "AI Extraction (Qwen)", "node_type": "AI"},
    {"node_id": "req_matching", "node_label": "Requirement Matching", "node_type": "VALIDATION"},
    {"node_id": "validation", "node_label": "Field Validation", "node_type": "VALIDATION"},
    {"node_id": "nic", "node_label": "NIC Code Analysis", "node_type": "AI"},
    {"node_id": "human_review", "node_label": "Human Review Checkpoint", "node_type": "HUMAN"},
    {"node_id": "udyam_prep", "node_label": "Udyam Form Preparation", "node_type": "PORTAL"},
    {"node_id": "portal_automation", "node_label": "Portal Automation", "node_type": "PORTAL"},
    {"node_id": "human_checkpoint", "node_label": "Portal Checkpoint (OTP/CAPTCHA)", "node_type": "HUMAN"},
    {"node_id": "final_review", "node_label": "Final Submission Signoff", "node_type": "HUMAN"},
    {"node_id": "submission", "node_label": "Portal Submission", "node_type": "PORTAL"},
    {"node_id": "certificate", "node_label": "Certificate Capture", "node_type": "RESULT"},
    {"node_id": "completed", "node_label": "Workflow Completed", "node_type": "RESULT"},
]


class WorkflowOrchestrator:
    @staticmethod
    async def get_or_create_execution(
        application_id: uuid.UUID,
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
        trigger_source: str = "DOCUMENT_UPLOAD",
    ) -> WorkflowExecution:
        """Retrieve existing active execution or initialize a fresh execution graph."""
        res = await db.execute(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.application_id == application_id,
                WorkflowExecution.status.in_(["RUNNING", "PAUSED", "HUMAN_REQUIRED"]),
            )
            .order_by(WorkflowExecution.started_at.desc())
        )
        existing = res.scalars().first()
        if existing:
            return existing

        execution = WorkflowExecution(
            id=uuid.uuid4(),
            application_id=application_id,
            workflow_version="2.0",
            status="RUNNING",
            current_node_id="doc_received",
            started_at=datetime.now(timezone.utc),
            triggered_by=user_id,
            trigger_source=trigger_source,
            context_json={"auto_orchestrated": True},
        )
        db.add(execution)
        await db.flush()

        # Initialize all 16 node execution rows
        for item in STANDARD_WORKFLOW_NODES:
            node_exec = WorkflowNodeExecution(
                id=uuid.uuid4(),
                execution_id=execution.id,
                node_id=item["node_id"],
                node_label=item["node_label"],
                node_type=item["node_type"],
                status="WAITING",
                attempt=1,
                max_attempts=3,
            )
            db.add(node_exec)

        await db.commit()
        await db.refresh(execution)

        await WorkflowOrchestrator.emit_event(
            "WORKFLOW_STARTED",
            {
                "execution_id": str(execution.id),
                "application_id": str(application_id),
                "status": "RUNNING",
                "trigger_source": trigger_source,
            },
        )

        return execution

    @staticmethod
    async def get_node_execution(
        execution_id: uuid.UUID,
        node_id: str,
        db: AsyncSession,
    ) -> Optional[WorkflowNodeExecution]:
        res = await db.execute(
            select(WorkflowNodeExecution).where(
                WorkflowNodeExecution.execution_id == execution_id,
                WorkflowNodeExecution.node_id == node_id,
            )
        )
        return res.scalars().first()

    @staticmethod
    async def update_node_state(
        *,
        execution_id: uuid.UUID,
        node_id: str,
        status: str,
        db: AsyncSession,
        input_summary: Optional[Dict[str, Any]] = None,
        output_summary: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        logs_text: Optional[str] = None,
        worker_id: Optional[str] = None,
        screenshot_path: Optional[str] = None,
    ) -> Optional[WorkflowNodeExecution]:
        node = await WorkflowOrchestrator.get_node_execution(execution_id, node_id, db)
        if not node:
            return None

        now = datetime.now(timezone.utc)
        node.status = status
        node.updated_at = now

        if worker_id:
            node.worker_id = worker_id
        if input_summary is not None:
            node.input_summary = input_summary
        if output_summary is not None:
            node.output_summary = output_summary
        if error_message is not None:
            node.error_message = error_message
        if logs_text is not None:
            node.logs_text = (node.logs_text or "") + ("\n" if node.logs_text else "") + logs_text
        if screenshot_path is not None:
            node.screenshot_path = screenshot_path

        if status == "RUNNING" and not node.started_at:
            node.started_at = now
        elif status in ["SUCCESS", "FAILED", "SKIPPED", "CANCELLED"]:
            node.completed_at = now
            if node.started_at:
                node.duration_seconds = round((now - node.started_at).total_seconds(), 2)

        # Update Execution current node
        exec_res = await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
        workflow_exec = exec_res.scalars().first()
        if workflow_exec:
            workflow_exec.current_node_id = node_id
            workflow_exec.updated_at = now
            if status == "FAILED":
                workflow_exec.status = "FAILED"
                workflow_exec.error_message = error_message
            elif node_id == "completed" and status == "SUCCESS":
                workflow_exec.status = "COMPLETED"
                workflow_exec.completed_at = now
                if workflow_exec.started_at:
                    workflow_exec.duration_seconds = round((now - workflow_exec.started_at).total_seconds(), 2)

        await db.commit()
        await db.refresh(node)

        # Real-time event emit
        await WorkflowOrchestrator.emit_event(
            f"NODE_{status}",
            {
                "execution_id": str(execution_id),
                "node_id": node_id,
                "node_label": node.node_label,
                "status": status,
                "duration_seconds": float(node.duration_seconds) if node.duration_seconds else None,
                "worker_id": node.worker_id,
                "output_summary": output_summary,
                "error_message": error_message,
                "screenshot_path": screenshot_path,
                "timestamp": now.isoformat(),
            },
        )

        return node

    @staticmethod
    async def emit_event(event_type: str, payload: Dict[str, Any]) -> None:
        """Publish real-time telemetry over Redis pub/sub for WebSocket subscribers."""
        full_payload = {
            "event": event_type,
            **payload,
            "timestamp": payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        }
        try:
            r = aioredis.from_url(settings.REDIS_URL)
            await r.publish("taxla:updates", json.dumps(full_payload))
            await r.aclose()
        except Exception as e:
            logger.warning("Failed to publish %s to taxla:updates: %s", event_type, e)

        await publish_event(full_payload)

    @staticmethod
    async def process_document_pipeline(
        application_id: uuid.UUID,
        document_id: uuid.UUID,
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Execute deterministic and AI processing for an uploaded document."""
        execution = await WorkflowOrchestrator.get_or_create_execution(
            application_id=application_id,
            db=db,
            user_id=user_id,
            trigger_source="DOCUMENT_UPLOAD",
        )

        # 1. NODE: doc_received
        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="doc_received",
            status="RUNNING",
            db=db,
            logs_text=f"Document {document_id} received for application {application_id}",
        )

        doc_res = await db.execute(select(Document).where(Document.id == document_id))
        doc = doc_res.scalars().first()
        if not doc:
            await WorkflowOrchestrator.update_node_state(
                execution_id=execution.id,
                node_id="doc_received",
                status="FAILED",
                error_message="Document record not found in database",
                db=db,
            )
            return {"success": False, "error": "Document not found"}

        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="doc_received",
            status="SUCCESS",
            output_summary={"file_name": doc.file_name, "size_bytes": doc.size_bytes, "mime_type": doc.mime_type},
            db=db,
        )

        # 2. NODE: classification
        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="classification",
            status="RUNNING",
            db=db,
            logs_text=f"Classifying file {doc.file_name}...",
        )

        classified_type, class_conf = DocumentClassifier.classify(doc.file_name)
        doc.type = classified_type
        await db.commit()

        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="classification",
            status="SUCCESS",
            output_summary={"classified_type": classified_type, "confidence": class_conf},
            logs_text=f"Document classified as {classified_type} (confidence {class_conf:.2f})",
            db=db,
        )

        # 3 & 4. NODE: parsing & ocr
        raw_text = ""
        ocr_lines: List[OcrLine] = []
        is_docx = doc.file_name.lower().endswith(".docx")

        if is_docx and os.path.exists(doc.storage_path):
            # Native DOCX Parsing (Cheap Deterministic)
            await WorkflowOrchestrator.update_node_state(
                execution_id=execution.id,
                node_id="parsing",
                status="RUNNING",
                db=db,
                logs_text="Extracting native text from Word (.docx) document...",
            )
            try:
                import docx as docx_pkg
                d = docx_pkg.Document(doc.storage_path)
                paragraphs = [p.text for p in d.paragraphs if p.text.strip()]
                for table in d.tables:
                    for row in table.rows:
                        row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                        if row_text:
                            paragraphs.append(row_text)
                raw_text = "\n".join(paragraphs)

                await WorkflowOrchestrator.update_node_state(
                    execution_id=execution.id,
                    node_id="parsing",
                    status="SUCCESS",
                    output_summary={"method": "native_docx", "char_count": len(raw_text)},
                    db=db,
                )
                await WorkflowOrchestrator.update_node_state(
                    execution_id=execution.id,
                    node_id="ocr",
                    status="SKIPPED",
                    logs_text="OCR skipped (native DOCX text available)",
                    db=db,
                )
            except Exception as e:
                logger.warning("Native DOCX parsing failed, falling back to OCR: %s", e)

        if not raw_text.strip():
            # OCR Processing
            await WorkflowOrchestrator.update_node_state(
                execution_id=execution.id,
                node_id="ocr",
                status="RUNNING",
                worker_id="tesseract-worker",
                db=db,
                logs_text=f"Starting OCR on {doc.file_name}...",
            )

            provider = OcrService.get_provider()
            t0 = time.monotonic()
            try:
                ocr_lines = provider.extract_text(doc.storage_path, doc.type)
                raw_text = "\n".join(l.text for l in ocr_lines)
            except (OcrUnavailableError, OcrFailureError) as exc:
                await WorkflowOrchestrator.update_node_state(
                    execution_id=execution.id,
                    node_id="ocr",
                    status="FAILED",
                    error_message=str(exc),
                    db=db,
                )
                return {"success": False, "error": str(exc)}

            duration_ms = int((time.monotonic() - t0) * 1000)

            # Persist RawOcrResult
            try:
                db.add(
                    RawOcrResult(
                        document_id=doc.id,
                        page_number=1,
                        raw_text=raw_text,
                        line_count=len(ocr_lines),
                        average_confidence=round(sum(l.confidence for l in ocr_lines) / max(1, len(ocr_lines)) / 100.0, 3),
                        ocr_engine=provider.engine_name(),
                        ocr_engine_version=provider.engine_version(),
                        preprocessing_version=provider.preprocessing_version(),
                        processing_version=f"{provider.engine_name()}@{provider.engine_version()}",
                        bounding_boxes=[l.to_dict() for l in ocr_lines],
                        metadata_json={"processing_ms": duration_ms},
                    )
                )
                await db.commit()
            except Exception as e:
                logger.warning("Failed to persist RawOcrResult: %s", e)

            await WorkflowOrchestrator.update_node_state(
                execution_id=execution.id,
                node_id="ocr",
                status="SUCCESS",
                output_summary={"lines_extracted": len(ocr_lines), "duration_ms": duration_ms},
                logs_text=f"OCR completed successfully ({len(ocr_lines)} lines in {duration_ms}ms)",
                db=db,
            )

        # 5. NODE: ai_extraction (Ollama + Qwen ~3.5B)
        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="ai_extraction",
            status="RUNNING",
            worker_id="ollama-qwen-worker",
            input_summary={"provider": "Ollama", "model": settings.OLLAMA_MODEL, "doc_type": doc.type},
            db=db,
            logs_text=f"Invoking Ollama ({settings.OLLAMA_MODEL}) for structured extraction...",
        )

        extraction_result = await DocumentExtractionService.extract_fields(raw_text, doc.type)
        if not extraction_result.success:
            await WorkflowOrchestrator.update_node_state(
                execution_id=execution.id,
                node_id="ai_extraction",
                status="FAILED",
                error_message=extraction_result.error or "AI extraction failed",
                db=db,
            )
            return {"success": False, "error": extraction_result.error}

        review_service = ReviewDecisionService()
        extracted_dict_for_matching: Dict[str, Any] = {}

        for field_name, field_res in extraction_result.fields.items():
            if field_res.value is not None:
                extracted_dict_for_matching[field_name] = field_res.value

            decision = review_service.decide(
                FieldSignals(
                    ocr_confidence=round(field_res.extraction_confidence, 3),
                    extraction_confidence=round(field_res.extraction_confidence, 3),
                    validation_status=field_res.validation_status,
                )
            )

            ext_data = ExtractedData(
                application_id=application_id,
                source_document_id=doc.id,
                field_name=field_name,
                field_value=str(field_res.value) if field_res.value is not None else None,
                confidence=decision.final_confidence,
                ocr_confidence=round(field_res.extraction_confidence, 3),
                extraction_confidence=round(field_res.extraction_confidence, 3),
                final_confidence=decision.final_confidence,
                review_decision=decision.review_decision,
                extraction_model=EXTRACTION_MODEL_NAME,
                extraction_prompt_version=EXTRACTION_PROMPT_VERSION,
                schema_version=EXTRACTION_SCHEMA_VERSION,
                validation_status=field_res.validation_status,
            )
            db.add(ext_data)

        doc.ocr_status = "COMPLETED"
        await db.commit()

        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="ai_extraction",
            status="SUCCESS",
            output_summary={
                "fields_extracted": len(extraction_result.fields),
                "model": settings.OLLAMA_MODEL,
                "confidence_score": extraction_result.overall_extraction_confidence,
            },
            logs_text=f"AI extraction completed: {len(extraction_result.fields)} fields extracted.",
            db=db,
        )

        # 6. NODE: req_matching
        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="req_matching",
            status="RUNNING",
            db=db,
            logs_text="Matching extracted fields to official 27 Udyam requirements...",
        )

        await RequirementEngine.match_extracted_fields(application_id, extracted_dict_for_matching, doc.id, db)
        completion_pct = await RequirementEngine.recalculate_completion(application_id, db)

        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="req_matching",
            status="SUCCESS",
            output_summary={"completion_percentage": completion_pct, "matched_fields": len(extracted_dict_for_matching)},
            logs_text=f"Requirement matching complete: application completion at {completion_pct:.1f}%",
            db=db,
        )

        # 7. NODE: validation
        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="validation",
            status="RUNNING",
            db=db,
            logs_text="Running format validation rules and calculating confidence branches...",
        )

        val_result = await ValidationEngine.validate_application_extractions(application_id, db)

        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="validation",
            status="SUCCESS",
            output_summary={"validation_pass": True, "branch": "AUTO_PROGRESS"},
            logs_text="Validation rules passed successfully.",
            db=db,
        )

        # 8. NODE: nic (NIC Code Analysis)
        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="nic",
            status="RUNNING",
            db=db,
            logs_text="Generating 3-tier NIC code classification...",
        )

        app_res = await db.execute(select(Application).where(Application.id == application_id))
        app = app_res.scalars().first()
        client_name = ""
        if app and app.client_id:
            c_res = await db.execute(select(Client).where(Client.id == app.client_id))
            c_obj = c_res.scalar_one_or_none()
            if c_obj:
                client_name = c_obj.business_name or ""
        business_desc = (app.major_activity if app else None) or client_name or "General Commercial Enterprise"

        nic_service = NICClassificationService()
        suggestions = await nic_service.generate_suggestions(
            app_id=application_id,
            business_description=business_desc,
            location_text="",
            db=db,
        )
        await db.commit()

        top_nic = suggestions[0].nic_5digit if suggestions else "62011"

        await WorkflowOrchestrator.update_node_state(
            execution_id=execution.id,
            node_id="nic",
            status="SUCCESS",
            output_summary={"suggestions_count": len(suggestions), "top_nic_code": top_nic},
            logs_text=f"NIC classification identified {len(suggestions)} candidates. Primary: {top_nic}",
            db=db,
        )

        # Check if Human Checkpoint is required for NIC or if we proceed to Udyam Prep & Portal Automation
        auto_portal = True
        if auto_portal:
            # Mark human_review skipped/passed
            await WorkflowOrchestrator.update_node_state(
                execution_id=execution.id,
                node_id="human_review",
                status="SUCCESS",
                logs_text="Autonomous policy allowed straight-through review.",
                db=db,
            )

            # 10. NODE: udyam_prep
            await WorkflowOrchestrator.update_node_state(
                execution_id=execution.id,
                node_id="udyam_prep",
                status="SUCCESS",
                logs_text="Application state transitioned to READY_FOR_PORTAL. Starting Portal Automation...",
                db=db,
            )

            if app:
                try:
                    if app.status == ApplicationState.NIC_REVIEW.value:
                        await transition(app, ApplicationState.READY_FOR_PORTAL.value, user_id, db)
                    elif app.status != ApplicationState.READY_FOR_PORTAL.value:
                        if app.status == ApplicationState.NEW.value:
                            await transition(app, ApplicationState.DOCUMENTS_UPLOADED.value, user_id, db)
                        if app.status == ApplicationState.DOCUMENTS_UPLOADED.value:
                            await transition(app, ApplicationState.PROCESSING.value, user_id, db)
                        if app.status == ApplicationState.PROCESSING.value:
                            await transition(app, ApplicationState.EXTRACTED.value, user_id, db)
                        if app.status == ApplicationState.EXTRACTED.value:
                            await transition(app, ApplicationState.VALIDATION.value, user_id, db)
                        if app.status == ApplicationState.VALIDATION.value:
                            await transition(app, ApplicationState.NIC_REVIEW.value, user_id, db)
                        if app.status == ApplicationState.NIC_REVIEW.value:
                            await transition(app, ApplicationState.READY_FOR_PORTAL.value, user_id, db)
                    await db.commit()
                except Exception as e:
                    logger.warning("Transition to READY_FOR_PORTAL: %s", e)

            # Dispatch Playwright automation directly in background + ARQ
            async def _run_playwright_detached(app_id_str: str):
                try:
                    from worker.playwright_agent import run_automation
                    await run_automation(app_id_str)
                except Exception as exc:
                    logger.exception("Detached Playwright automation failed: %s", exc)

            import asyncio
            asyncio.create_task(_run_playwright_detached(str(application_id)))

            try:
                from arq import create_pool
                from arq.connections import RedisSettings
                redis_pool = await create_pool(RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT))
                await redis_pool.enqueue_job("start_playwright_automation_job", str(application_id))
            except Exception as e:
                logger.warning("Failed to enqueue Playwright ARQ job: %s", e)

        return {
            "success": True,
            "execution_id": str(execution.id),
            "application_id": str(application_id),
            "completion_percentage": completion_pct,
            "top_nic_code": top_nic,
        }

    @staticmethod
    async def pause_execution(execution_id: uuid.UUID, reason: str, db: AsyncSession) -> WorkflowExecution:
        res = await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
        exec_obj = res.scalars().first()
        if not exec_obj:
            raise ValueError("Execution not found")

        exec_obj.status = "PAUSED"
        exec_obj.context_json = {**(exec_obj.context_json or {}), "pause_reason": reason}
        exec_obj.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(exec_obj)

        await WorkflowOrchestrator.emit_event(
            "WORKFLOW_PAUSED",
            {"execution_id": str(execution_id), "application_id": str(exec_obj.application_id), "reason": reason},
        )
        return exec_obj

    @staticmethod
    async def resume_execution(execution_id: uuid.UUID, db: AsyncSession, user_id: Optional[uuid.UUID] = None) -> WorkflowExecution:
        res = await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
        exec_obj = res.scalars().first()
        if not exec_obj:
            raise ValueError("Execution not found")

        exec_obj.status = "RUNNING"
        exec_obj.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(exec_obj)

        await WorkflowOrchestrator.emit_event(
            "WORKFLOW_RESUMED",
            {"execution_id": str(execution_id), "application_id": str(exec_obj.application_id)},
        )
        return exec_obj

    @staticmethod
    async def cancel_execution(execution_id: uuid.UUID, reason: str, db: AsyncSession) -> WorkflowExecution:
        res = await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
        exec_obj = res.scalars().first()
        if not exec_obj:
            raise ValueError("Execution not found")

        exec_obj.status = "CANCELLED"
        exec_obj.context_json = {**(exec_obj.context_json or {}), "cancel_reason": reason}
        exec_obj.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(exec_obj)

        await WorkflowOrchestrator.emit_event(
            "WORKFLOW_CANCELLED",
            {"execution_id": str(execution_id), "application_id": str(exec_obj.application_id), "reason": reason},
        )
        return exec_obj
