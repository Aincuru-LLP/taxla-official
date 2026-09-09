"""Phase 07 — Certificate API.

Endpoints:
  * ``GET /api/v1/applications/{id}/certificate`` — serves the registration
    certificate PDF.
    - If the application is not in ``COMPLETED`` (or the certificate
      file is missing on disk): ``409 Conflict`` with
      ``{"message": "Application not yet completed"}``.
    - If everything is in place: ``200`` with ``Content-Type: application/pdf``
      streaming the file from ``settings.CERTIFICATES_DIR/<id>.pdf``.

  * ``POST /api/v1/applications/{id}/certificate/generate`` — convenience
    endpoint that lets REVIEWER_AUDITOR+ force a placeholder regeneration
    if the file went missing (e.g. cleared storage between deploys).
    Idempotent: writes the file if missing, overwrites if present.

RBAC:
  * GET — any role with branch access (the same matrix as GET /applications/{id}).
    OPERATOR, REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
  * POST regenerate — REVIEWER_AUDITOR+ (BRANCH_ADMIN + SUPER_ADMIN also).

Branch scope: enforced via ``assert_branch_scope`` so cross-branch reads
are 403 just like the application itself.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_async_db
from app.core.security import assert_branch_scope, get_current_user, require_roles
from app.models.domain import Application, Certificate, User
from app.models.state import ApplicationState
from app.services.certificate_generator import generate_certificate_pdf

router = APIRouter(
    prefix="/applications",
    tags=["Certificates"],
)


def _certificate_path(application_id: uuid.UUID) -> str:
    return os.path.join(settings.CERTIFICATES_DIR, f"{application_id}.pdf")


async def _get_application_or_404(
    db: AsyncSession, application_id: uuid.UUID
) -> Application:
    # Eager-load ``client`` because after the endpoint commits the
    # async session expires instances, and lazy-loading the relationship
    # later would raise MissingGreenlet (no sync DBAPI to fall back to).
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(selectinload(Application.client))
    )
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


async def _populate_certificate_row(
    db: AsyncSession,
    application: Application,
    *,
    file_path: str,
    registration_number: str,
) -> Certificate:
    """Insert or update the ``certificates`` row matching ``application``.

    The table has a unique constraint on ``application_id`` so we always
    SELECT-then-INSERT-or-UPDATE rather than relying on ON CONFLICT, which
    would couple us to a specific dialect.
    """
    result = await db.execute(
        select(Certificate).where(Certificate.application_id == application.id)
    )
    cert = result.scalars().first()
    if cert is None:
        cert = Certificate(
            application_id=application.id,
            registration_number=registration_number,
            file_path=file_path,
            issued_at=datetime.now(timezone.utc),
        )
        db.add(cert)
    else:
        cert.file_path = file_path
        cert.registration_number = registration_number
        cert.issued_at = datetime.now(timezone.utc)
    await db.flush()
    return cert


@router.get(
    "/{id}/certificate",
    response_class=FileResponse,
)
async def get_certificate(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the certificate PDF for ``id``.

    Allowed roles: any role with branch access (the same matrix as GET
    /applications/{id}). Branch scope: enforced via ``assert_branch_scope``.
    """
    application = await _get_application_or_404(db, id)
    await assert_branch_scope(current_user, application)

    # "Application not yet completed" — the canonical 409 message per
    # the Phase 07 plan. We surface this whenever the workflow has not
    # reached COMPLETED *or* the file is missing on disk.
    if application.status != ApplicationState.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application not yet completed",
        )

    file_path = _certificate_path(id)
    if not os.path.exists(file_path):
        # The DB may have a row pointing at a file that was wiped from
        # storage. The "regenerate" endpoint can rebuild it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application not yet completed",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"{application.application_number}.pdf",
    )


@router.post(
    "/{id}/certificate/generate",
    status_code=status.HTTP_200_OK,
)
async def generate_certificate(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(
        require_roles("REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN")
    ),
):
    """Phase 07 — placeholder certificate regeneration.

    Writes ``storage/certificates/<id>.pdf`` and inserts/updates the
    matching ``certificates`` row. Useful when the file was lost (deploy
    wiped storage) or when an admin wants to refresh the placeholder
    after a manual correction.

    Allowed roles: REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    """
    application = await _get_application_or_404(db, id)
    await assert_branch_scope(current_user, application)

    file_path = _certificate_path(id)

    # Load applicant details so the PDF is meaningful.
    applicant_name = application.client.applicant_name if application.client else "(unknown)"
    pan_number = application.client.pan_number if application.client else "(unknown)"
    business_name = application.client.business_name if application.client else "(unknown)"

    # Generate the placeholder PDF. The official certificate overwrites
    # this once Phase 09 captures it from the Udyam portal.
    written = generate_certificate_pdf(
        application_id=str(id),
        application_number=application.application_number,
        business_name=business_name,
        applicant_name=applicant_name,
        pan_number=pan_number,
        registration_number=f"UDYAM-{application.application_number}",
        output_path=file_path,
    )

    cert = await _populate_certificate_row(
        db,
        application,
        file_path=written,
        registration_number=f"UDYAM-{application.application_number}",
    )
    await db.commit()

    return {
        "status": "success",
        "certificate_id": str(cert.id),
        "file_path": written,
        "registration_number": cert.registration_number,
    }