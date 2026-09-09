import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_db
from app.core.security import get_current_user, require_roles, assert_branch_scope
from app.models.domain import (
    Application,
    AuditLog,
    Certificate,
    NicReview,
    NICSuggestion,
    User,
    Workflow,
)
from app.schemas.workflow import (
    FinalReviewRequest,
    NICApproveRequest,
    NICRejectRequest,
    NICSearchRequest,
    OTPInputRequest,
    ValidationReviewRequest,
)
from app.models.state import ApplicationState
from app.core.state_machine import transition
from app.services.nic_service import NICClassificationService
from app.services.validation_engine import ValidationEngine

router = APIRouter(prefix="/applications", tags=["Workflow"])

@router.post("/{id}/nic/search", status_code=status.HTTP_200_OK)
async def search_nic(
    id: uuid.UUID,
    request: NICSearchRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Search NIC classifications for an application.

    Allowed roles: OPERATOR, REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    """
    result = await db.execute(select(Application).where(Application.id == id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    service = NICClassificationService()
    candidates = await service.generate_suggestions(
        app_id=id,
        business_description=request.business_description,
        location_text=request.location_text or "",
        db=db
    )

    await db.commit()

    return {
        "status": "success",
        "suggestions": [cand.model_dump() for cand in candidates]
    }


@router.post("/{id}/nic/approve", status_code=status.HTTP_200_OK)
async def approve_nic(
    id: uuid.UUID,
    request: NICApproveRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Phase 07 — Reviewer approves the NIC classification.

    Body: ``{ selected_codes: ["12345", ...], justification: "..." }``.
    Writes a ``NicReview`` row with ``decision='APPROVE'`` and persists
    each code as an approved ``NICSuggestion`` (so downstream code can
    read the chosen 5-digit codes without joining through the review).
    Transitions ``NIC_REVIEW → READY_FOR_PORTAL``.

    Allowed roles: REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    OPERATOR is explicitly forbidden per documents/04.
    """
    result = await db.execute(select(Application).where(Application.id == id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    if app.status != ApplicationState.NIC_REVIEW.value:
        raise HTTPException(
            status_code=400,
            detail=f"Application is in {app.status}, not NIC_REVIEW",
        )

    # Normalise + validate the codes. Pydantic's ``min_length=1`` on
    # ``selected_codes`` catches "empty list"; here we reject malformed
    # 5-digit strings so a typo can't slip into the audit log.
    cleaned_codes: list[str] = []
    for code in request.selected_codes:
        code = code.strip()
        if not (len(code) == 5 and code.isdigit()):
            raise HTTPException(
                status_code=400,
                detail=f"NIC code '{code}' is not a 5-digit string",
            )
        cleaned_codes.append(code)

    # Persist each approved code as an NICSuggestion so the application
    # row still has a denormalised list of chosen NIC codes for queries
    # that don't want to join through nic_reviews.
    for code in cleaned_codes:
        db.add(NICSuggestion(
            application_id=id,
            nic_code_2digit=code[:2],
            nic_code_4digit=code[:4],
            nic_code_5digit=code,
            description="Reviewer-approved NIC code",
            confidence=1.0,
            rationale=request.justification,
            approved=True,
            selected_by=current_user.id,
        ))

    # NicReview row captures the decision + justification for the audit
    # trail. SELECTED_CODES lives in JSONB so multi-code applicants work.
    db.add(NicReview(
        application_id=id,
        reviewer_id=current_user.id,
        selected_codes=cleaned_codes,
        justification=request.justification,
        decision="APPROVE",
    ))

    await transition(
        app,
        ApplicationState.READY_FOR_PORTAL.value,
        current_user.id,
        db,
        payload_json={"selected_codes": cleaned_codes},
    )
    await db.commit()

    return {
        "status": "success",
        "decision": "approve",
        "selected_codes": cleaned_codes,
        "new_state": ApplicationState.READY_FOR_PORTAL.value,
    }


@router.post("/{id}/nic/reject", status_code=status.HTTP_200_OK)
async def reject_nic(
    id: uuid.UUID,
    request: NICRejectRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Phase 07 — Reviewer rejects the NIC classification.

    Body: ``{ justification: "..." }``.
    Writes a ``NicReview`` row with ``decision='REJECT'`` and transitions
    ``NIC_REVIEW → DATA_VERIFICATION`` so the operator can re-classify
    with corrected business-description text.

    Allowed roles: REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    """
    result = await db.execute(select(Application).where(Application.id == id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    if app.status != ApplicationState.NIC_REVIEW.value:
        raise HTTPException(
            status_code=400,
            detail=f"Application is in {app.status}, not NIC_REVIEW",
        )

    # The justification is required (Pydantic min_length=1) but we also
    # save the prior suggestion IDs in the NicReview.selected_codes list
    # so an audit reader can see "the reviewer saw codes X, Y, Z and
    # rejected them all because Z".
    prior_codes: list[str] = []
    prior = await db.execute(
        select(NICSuggestion).where(NICSuggestion.application_id == id)
    )
    for sug in prior.scalars().all():
        prior_codes.append(sug.nic_code_5digit)

    db.add(NicReview(
        application_id=id,
        reviewer_id=current_user.id,
        selected_codes=prior_codes,
        justification=request.justification,
        decision="REJECT",
    ))

    await transition(
        app,
        ApplicationState.DATA_VERIFICATION.value,
        current_user.id,
        db,
        payload_json={"rejected_codes": prior_codes},
    )
    await db.commit()

    return {
        "status": "success",
        "decision": "reject",
        "rejected_codes": prior_codes,
        "new_state": ApplicationState.DATA_VERIFICATION.value,
    }


@router.post("/{id}/final-review", status_code=status.HTTP_200_OK)
async def final_review(
    id: uuid.UUID,
    request: FinalReviewRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Phase 07 — Final reviewer signoff before portal submission.

    Body: ``{ kyc_confirmed: bool, signoff_method: "DIGITAL_SIGNATURE"|"AADHAAR_OTP", remarks?: str }``.
    Writes a ``FinalReview`` row and transitions ``HUMAN_REVIEW → APPROVED``.

    Allowed roles: REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    """
    result = await db.execute(select(Application).where(Application.id == id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    if app.status != ApplicationState.HUMAN_REVIEW.value:
        raise HTTPException(
            status_code=400,
            detail=f"Application is in {app.status}, not HUMAN_REVIEW",
        )

    from app.models.domain import FinalReview

    db.add(FinalReview(
        application_id=id,
        reviewer_id=current_user.id,
        kyc_confirmed=request.kyc_confirmed,
        signoff_method=request.signoff_method,
        remarks=request.remarks,
    ))

    await transition(
        app,
        ApplicationState.APPROVED.value,
        current_user.id,
        db,
        payload_json={
            "signoff_method": request.signoff_method,
            "kyc_confirmed": request.kyc_confirmed,
        },
    )
    await db.commit()

    return {
        "status": "success",
        "decision": "approve",
        "new_state": ApplicationState.APPROVED.value,
        "signoff_method": request.signoff_method,
    }


@router.post("/{id}/otp", status_code=status.HTTP_200_OK)
async def submit_otp(
    id: uuid.UUID,
    payload: OTPInputRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles("OPERATOR", "BRANCH_ADMIN", "SUPER_ADMIN"))
):
    """Human-in-the-loop OTP entry on the Udyam portal.

    Allowed roles: OPERATOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    """
    result = await db.execute(select(Application).where(Application.id == id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    if app.status != ApplicationState.OTP_REQUIRED.value:
        raise HTTPException(status_code=400, detail="Application not waiting for OTP")

    await transition(app, ApplicationState.OTP_VERIFIED.value, current_user.id, db)

    # Dispatch Redis Pub/Sub signal to resume worker
    import redis.asyncio as redis
    from app.core.config import settings
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    await r.publish(f"otp_{id}", payload.otp_code)

    await db.commit()
    return {"message": "OTP submitted", "status": app.status}


@router.patch("/{id}/validation-review", status_code=status.HTTP_200_OK)
async def review_validation(
    id: uuid.UUID,
    request: ValidationReviewRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Phase 04: REVIEWER_AUDITOR override on the MEDIUM-confidence path.

    The application must currently be in ``VALIDATION_REVIEW``. Approving
    transitions to ``NIC_REVIEW`` (auto-validated); rejecting transitions to
    ``HUMAN_REVIEW_REQUIRED`` (operator re-uploads).

    Allowed roles: REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    """
    result = await db.execute(select(Application).where(Application.id == id))
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    if app.status != ApplicationState.VALIDATION_REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Application is in {app.status}; review override only valid "
                f"from VALIDATION_REVIEW"
            ),
        )

    out = await ValidationEngine.override_validation_review(
        id, approve=request.approve, actor_id=current_user.id, db=db
    )
    return {
        "status": "success",
        "decision": "approve" if request.approve else "reject",
        "new_state": out.get("new_state"),
    }


@router.post("/{id}/submit", status_code=status.HTTP_200_OK)
async def submit_application(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(
        "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN"
    ))
):
    """Phase 07 — submit an APPROVED application.

    Drives APPROVED → SUBMITTING → SUBMITTED. The transition into SUBMITTED
    also populates the ``certificates`` table with a placeholder PDF (the
    real certificate is captured from the Udyam portal by the Playwright
    worker — Phase 09 — and replaces this placeholder when the workflow
    reaches COMPLETED).

    Allowed roles: REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN.
    Branch scope: enforced via ``assert_branch_scope``.
    """
    # Eager-load the Client because the commit below will expire the
    # instance, and lazy-loading ``app.client`` afterwards would raise
    # MissingGreenlet (no sync DBAPI in async).
    result = await db.execute(
        select(Application)
        .where(Application.id == id)
        .options(selectinload(Application.client))
    )
    app = result.scalars().first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await assert_branch_scope(current_user, app)

    if app.status != ApplicationState.APPROVED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Application is in {app.status}, not APPROVED",
        )

    # APPROVED → SUBMITTING
    await transition(
        app,
        ApplicationState.SUBMITTING.value,
        current_user.id,
        db,
    )
    await db.flush()

    # SUBMITTING → SUBMITTED. We could let a worker do this asynchronously,
    # but Phase 07 keeps the submit synchronous — the portal worker takes
    # over once SUBMITTED transitions through AADHAAR_OTP/PAN_VERIFICATION
    # toward COMPLETED.
    await transition(
        app,
        ApplicationState.SUBMITTED.value,
        current_user.id,
        db,
    )

    # Populate the certificates table at SUBMITTED per the Phase 07 plan.
    # The placeholder PDF gets overwritten by the real capture in Phase 09.
    from app.core.config import settings
    from app.services.certificate_generator import generate_certificate_pdf

    file_path = os.path.join(settings.CERTIFICATES_DIR, f"{app.id}.pdf")
    applicant_name = app.client.applicant_name if app.client else "(unknown)"
    pan_number = app.client.pan_number if app.client else "(unknown)"
    business_name = app.client.business_name if app.client else "(unknown)"

    written = generate_certificate_pdf(
        application_id=str(app.id),
        application_number=app.application_number,
        business_name=business_name,
        applicant_name=applicant_name,
        pan_number=pan_number,
        registration_number=f"UDYAM-{app.application_number}",
        output_path=file_path,
    )

    # Upsert the Certificate row.
    cert_result = await db.execute(
        select(Certificate).where(Certificate.application_id == app.id)
    )
    cert = cert_result.scalars().first()
    if cert is None:
        cert = Certificate(
            application_id=app.id,
            registration_number=f"UDYAM-{app.application_number}",
            file_path=written,
            issued_at=datetime.now(timezone.utc),
        )
        db.add(cert)
    else:
        cert.file_path = written
        cert.registration_number = f"UDYAM-{app.application_number}"

    await db.commit()
    return {
        "status": "success",
        "new_state": ApplicationState.SUBMITTED.value,
        "certificate_path": written,
    }
