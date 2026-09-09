import logging
import os
import uuid
from typing import List, Optional

logger = logging.getLogger("taxla.api.documents")

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_db
from app.core.security import get_current_user, require_roles, assert_branch_scope
from app.core.config import settings
from app.core.state_machine import transition
from app.models.state import ApplicationState
from app.models.domain import User, Application, Document, AuditLog
from app.schemas.document import DocumentResponse

router = APIRouter(prefix="/applications", tags=["Documents"])

# Phase 14 — list docs across all applications in the caller's branch.
# Replaces the frontend hardcoded MOCK_DOCS array.
documents_router = APIRouter(prefix="/documents", tags=["Documents"])


@documents_router.get("", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    branch_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    )),
):
    """List documents across all applications in the caller's branch.

    Branch scope: SUPER_ADMIN may pass ``?branch_id=`` or omit it for
    all branches; everyone else is forced to their own branch.
    """
    if current_user.role == "SUPER_ADMIN":
        effective_branch_id = branch_id
    else:
        if branch_id is not None and branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=403,
                detail="Cross-branch listing denied: branch_id must match caller's branch",
            )
        effective_branch_id = current_user.branch_id

    # Join Application so we can filter by branch in one round trip.
    stmt = (
        select(Document)
        .join(Application, Application.id == Document.application_id)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if effective_branch_id is not None:
        stmt = stmt.where(Application.branch_id == effective_branch_id)

    rows = (await db.execute(stmt)).scalars().all()
    return [DocumentResponse.model_validate(d) for d in rows]


@router.get("/{id}/documents", response_model=List[DocumentResponse])
async def list_application_documents(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    )),
):
    """List every document uploaded against one application.

    Branch scope: enforced via ``assert_branch_scope`` against the
    parent application.
    """
    result = await db.execute(select(Application).where(Application.id == id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    rows = (
        await db.execute(
            select(Document)
            .where(Document.application_id == id)
            .order_by(Document.created_at.desc())
        )
    ).scalars().all()
    return [DocumentResponse.model_validate(d) for d in rows]

@router.post("/{id}/documents", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN"))
):
    """Upload a supporting document for an application.

    Allowed roles: OPERATOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    NOTE: REVIEWER_AUDITOR is forbidden here per documents/04 — they audit,
    they do not upload initial docs.
    """
    # Verify application exists + branch scope.
    result = await db.execute(select(Application).where(Application.id == id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    file_name = file.filename or "unknown"
    size_bytes = file.size or 0

    # Save file to disk
    doc_dir = os.path.join(settings.DOCUMENTS_DIR, str(id))
    os.makedirs(doc_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    save_path = os.path.join(doc_dir, f"{file_id}_{file_name}")

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    doc = Document(
        application_id=id,
        type=document_type,
        storage_path=save_path,
        file_name=file_name,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        ocr_status="PENDING"
    )
    db.add(doc)

    # Audit Log
    audit = AuditLog(
        actor_id=current_user.id,
        application_id=id,
        action="DOCUMENT_UPLOADED",
        metadata_json={"document_type": document_type, "file_name": file_name}
    )
    db.add(audit)

    await db.commit()
    await db.refresh(doc)

    # Transition State
    # Note: Transitioning state based on workflow requirement
    if app.status == ApplicationState.NEW.value:
        await transition(app, ApplicationState.DOCUMENTS_UPLOADED.value, current_user.id, db)
        await db.commit()

    # Phase 08 — emit DOCUMENT_UPLOADED so any matching trigger (e.g. the
    # seed ``seed-ocr-pipeline``) can react. ``publish_event`` is
    # best-effort and never raises, so a Redis hiccup won't fail the
    # upload.
    from app.core.events import publish_event
    await publish_event({
        "event": "DOCUMENT_UPLOADED",
        "application_id": str(id),
        "document_id": str(doc.id),
        "document_type": document_type,
        "branch_id": str(app.branch_id),
        "actor_id": str(current_user.id),
    })

    # Initialize Workflow Execution
    from app.services.workflow_orchestrator import WorkflowOrchestrator
    execution = await WorkflowOrchestrator.get_or_create_execution(
        application_id=id,
        db=db,
        user_id=current_user.id,
        trigger_source="DOCUMENT_UPLOAD",
    )

    # Dispatch pipeline runner in background
    async def _run_detached_pipeline_for_upload(target_app_id: uuid.UUID, target_doc_id: uuid.UUID, uid: Optional[uuid.UUID]):
        from app.core.database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as session:
                await WorkflowOrchestrator.process_document_pipeline(
                    application_id=target_app_id,
                    document_id=target_doc_id,
                    db=session,
                    user_id=uid,
                )
        except Exception as err:
            logger.exception("Detached pipeline task error: %s", err)

    import asyncio
    asyncio.create_task(_run_detached_pipeline_for_upload(id, doc.id, current_user.id))

    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        redis_pool = await create_pool(RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT))
        await redis_pool.enqueue_job('ocr_extraction_job', str(id), str(doc.id))
    except Exception as e:
        logger.warning("Failed to dispatch ARQ OCR job: %s", e)

    return DocumentResponse.model_validate(doc)


@documents_router.get("/{document_id}/preview")
async def preview_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Stream PDF or image for inline browser preview."""
    doc_res = await db.execute(select(Document).where(Document.id == document_id))
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="Document file missing on disk")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=doc.storage_path,
        media_type=doc.mime_type or "application/octet-stream",
        filename=doc.file_name,
        content_disposition_type="inline",
    )


@documents_router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Download the raw document file."""
    doc_res = await db.execute(select(Document).where(Document.id == document_id))
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="Document file missing on disk")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=doc.storage_path,
        media_type=doc.mime_type or "application/octet-stream",
        filename=doc.file_name,
        content_disposition_type="attachment",
    )


@documents_router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN")),
):
    """Re-trigger OCR and Ollama extraction for a document."""
    doc_res = await db.execute(select(Document).where(Document.id == document_id))
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.ocr_status = "PENDING"
    await db.commit()

    # Enqueue ARQ job
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        redis_pool = await create_pool(RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT))
        await redis_pool.enqueue_job('ocr_extraction_job', str(doc.application_id), str(doc.id))
    except Exception as e:
        print(f"Failed to dispatch OCR reprocess job: {e}")

    return {"success": True, "message": "OCR and extraction re-queued for document", "document_id": str(document_id)}


@documents_router.post("/autonomous-upload", status_code=status.HTTP_200_OK)
async def autonomous_document_upload(
    file: UploadFile = File(...),
    application_id: Optional[uuid.UUID] = Form(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN")),
):
    """Autonomous One-Click Document Upload.

    Auto-classifies document, resolves or creates the parent application,
    attaches document, initializes visualizer execution graph, and starts
    the pipeline immediately.
    """
    from app.services.document_classifier import DocumentClassifier
    from app.services.workflow_orchestrator import WorkflowOrchestrator
    from app.services.application_resolver import ApplicationResolver
    from app.models.domain import Client, OfficialAddress, Branch

    file_name = file.filename or "requirement_document.pdf"
    contents = await file.read()
    size_bytes = len(contents)

    # 1. Resolve or create application using ApplicationResolver
    branch_id = current_user.branch_id
    if not branch_id:
        first_branch = (await db.execute(select(Branch).limit(1))).scalars().first()
        branch_id = first_branch.id if first_branch else uuid.uuid4()

    # Try quick text sniff for PDF/text if available
    raw_sniff = ""
    try:
        raw_sniff = contents[:4096].decode("utf-8", errors="ignore")
    except Exception:
        pass

    resolution = await ApplicationResolver.resolve(
        raw_text=raw_sniff,
        filename=file_name,
        branch_id=branch_id,
        user_id=current_user.id,
        db=db,
        explicit_app_id=application_id,
        auto_create=True,
    )

    app_res = await db.execute(select(Application).where(Application.id == resolution.application_id))
    app = app_res.scalar_one()

    # Ensure official address exists
    addr_res = await db.execute(select(OfficialAddress).where(OfficialAddress.application_id == app.id))
    if not addr_res.scalar_one_or_none():
        off_addr = OfficialAddress(
            id=uuid.uuid4(),
            application_id=app.id,
            flat="",
            building="",
            city="",
            district="",
            state="",
            pin="",
        )
        db.add(off_addr)
        await db.commit()

    # 2. Save file
    doc_dir = os.path.join(settings.DOCUMENTS_DIR, str(app.id))
    os.makedirs(doc_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    save_path = os.path.join(doc_dir, f"{file_id}_{file_name}")

    with open(save_path, "wb") as f:
        f.write(contents)

    classified_type, _ = DocumentClassifier.classify(file_name)

    doc = Document(
        application_id=app.id,
        type=classified_type,
        storage_path=save_path,
        file_name=file_name,
        mime_type=file.content_type or "application/pdf",
        size_bytes=size_bytes,
        ocr_status="PENDING",
    )
    db.add(doc)

    audit = AuditLog(
        actor_id=current_user.id,
        application_id=app.id,
        action="AUTONOMOUS_DOCUMENT_UPLOADED",
        metadata_json={"document_type": classified_type, "file_name": file_name},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(doc)

    # 3. Transition & Initialize Workflow Execution
    if app.status == ApplicationState.NEW.value:
        await transition(app, ApplicationState.DOCUMENTS_UPLOADED.value, current_user.id, db)
        await db.commit()

    execution = await WorkflowOrchestrator.get_or_create_execution(
        application_id=app.id,
        db=db,
        user_id=current_user.id,
        trigger_source="DOCUMENT_UPLOAD",
    )

    # 4. Trigger Autonomous Pipeline in Background
    async def _run_detached_pipeline(target_app_id: uuid.UUID, target_doc_id: uuid.UUID, uid: Optional[uuid.UUID]):
        from app.core.database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as session:
                await WorkflowOrchestrator.process_document_pipeline(
                    application_id=target_app_id,
                    document_id=target_doc_id,
                    db=session,
                    user_id=uid,
                )
        except Exception as err:
            logger.exception("Detached pipeline task error: %s", err)

    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        redis_pool = await create_pool(RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT))
        await redis_pool.enqueue_job("ocr_extraction_job", str(app.id), str(doc.id))
    except Exception as e:
        logger.warning("Failed to dispatch ARQ OCR job: %s. Running detached background task.", e)
        import asyncio
        asyncio.create_task(_run_detached_pipeline(app.id, doc.id, current_user.id))

    # Safely fetch client business name
    client_res = await db.execute(select(Client).where(Client.id == app.client_id))
    matched_client = client_res.scalar_one_or_none()
    business_name = matched_client.business_name if matched_client else "MSME Application"

    return {
        "success": True,
        "message": "Document received. Autonomous automation started.",
        "application_id": str(app.id),
        "document_id": str(doc.id),
        "application_number": app.application_number,
        "business_name": business_name,
        "execution_id": str(execution.id),
        "visualizer_url": f"/applications/{app.id}/automation",
    }


@documents_router.get("/{document_id}/extracted-fields")
async def get_document_extracted_fields(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch structured fields extracted from this document."""
    from app.models.domain import ExtractedData
    fields_res = await db.execute(
        select(ExtractedData).where(ExtractedData.source_document_id == document_id)
    )
    fields = fields_res.scalars().all()

    return [
        {
            "id": str(f.id),
            "field_name": f.field_name,
            "field_value": f.field_value,
            "final_confidence": float(f.final_confidence) if f.final_confidence else None,
            "ocr_confidence": float(f.ocr_confidence) if f.ocr_confidence else None,
            "extraction_confidence": float(f.extraction_confidence) if f.extraction_confidence else None,
            "validation_status": f.validation_status,
            "review_decision": f.review_decision,
        }
        for f in fields
    ]

