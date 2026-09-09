"""API Router for 9-Section Requirement Documents and Generation."""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db as get_db
from app.core.security import get_current_user, require_roles
from app.models.domain import Application, GeneratedDocument, User
from app.services.generation_service import GenerationService
from app.services.template_service import TemplateService

router = APIRouter(tags=["Requirement Documents & Generation"])


class GenerateDocsRequest(BaseModel):
    custom_template_data: Optional[Dict[str, Any]] = None


class GeneratedDocItemResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    document_title: str
    format: str
    file_size_bytes: int
    status: str
    created_at: str


@router.get(
    "/applications/{application_id}/template-preview",
    dependencies=[Depends(require_roles("SUPER_ADMIN", "BRANCH_ADMIN", "OPERATOR", "REVIEWER_AUDITOR", "REVIEWER"))],
)
async def get_template_preview(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compile and return the live 9-section intake template JSON structure."""
    try:
        return await TemplateService.build_template_for_application(application_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/applications/{application_id}/requirement-documents",
    dependencies=[Depends(require_roles("SUPER_ADMIN", "BRANCH_ADMIN", "OPERATOR"))],
)
async def generate_requirement_documents(
    application_id: uuid.UUID,
    payload: Optional[GenerateDocsRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate server-side PDF and Word (.docx) requirement documents."""
    app_res = await db.execute(select(Application).where(Application.id == application_id))
    app = app_res.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    custom_data = payload.custom_template_data if payload else None
    pdf_doc, docx_doc = await GenerationService.generate_requirement_documents(
        application_id=application_id,
        db=db,
        user_id=current_user.id,
        custom_template_data=custom_data,
    )

    return {
        "success": True,
        "message": "Requirement documents generated successfully.",
        "documents": [
            {
                "id": str(pdf_doc.id),
                "title": pdf_doc.document_title,
                "format": pdf_doc.format,
                "size_bytes": pdf_doc.file_size_bytes,
                "download_url": f"/api/v1/requirement-documents/{pdf_doc.id}/download",
            },
            {
                "id": str(docx_doc.id),
                "title": docx_doc.document_title,
                "format": docx_doc.format,
                "size_bytes": docx_doc.file_size_bytes,
                "download_url": f"/api/v1/requirement-documents/{docx_doc.id}/download",
            },
        ],
    }


@router.get(
    "/applications/{application_id}/requirement-documents",
    dependencies=[Depends(require_roles("SUPER_ADMIN", "BRANCH_ADMIN", "OPERATOR", "REVIEWER_AUDITOR", "REVIEWER"))],
)
async def list_requirement_documents(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all generated requirement artifacts for an application."""
    docs_res = await db.execute(
        select(GeneratedDocument)
        .where(GeneratedDocument.application_id == application_id)
        .order_by(GeneratedDocument.created_at.desc())
    )
    docs = docs_res.scalars().all()

    return [
        {
            "id": str(d.id),
            "application_id": str(d.application_id),
            "document_title": d.document_title,
            "format": d.format,
            "file_size_bytes": d.file_size_bytes,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "download_url": f"/api/v1/requirement-documents/{d.id}/download",
        }
        for d in docs
    ]


@router.get("/requirement-documents/{document_id}/download")
async def download_requirement_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download a generated PDF or DOCX requirement artifact."""
    doc_res = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == document_id))
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Generated document not found")

    if not os.path.exists(doc.storage_path):
        raise HTTPException(status_code=404, detail="Document file missing on disk")

    ext = "pdf" if doc.format == "PDF" else "docx"
    media_type = "application/pdf" if doc.format == "PDF" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    filename = f"{doc.document_title.replace(' ', '_')}.{ext}"

    return FileResponse(
        path=doc.storage_path,
        media_type=media_type,
        filename=filename,
    )


@router.post(
    "/requirement-documents/{document_id}/send",
    dependencies=[Depends(require_roles("SUPER_ADMIN", "BRANCH_ADMIN", "OPERATOR"))],
)
async def mark_document_sent(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a requirement document as dispatched/sent to the client."""
    doc_res = await db.execute(select(GeneratedDocument).where(GeneratedDocument.id == document_id))
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Generated document not found")

    doc.status = "SENT"
    await db.commit()
    return {"success": True, "document_id": str(doc.id), "status": doc.status}
