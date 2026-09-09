from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

class NICSearchRequest(BaseModel):
    business_description: str
    location_text: Optional[str] = None

class OTPInputRequest(BaseModel):
    otp_code: str = Field(..., pattern=r"^[0-9]{6}$")


class ValidationReviewRequest(BaseModel):
    """Phase 04: REVIEWER override on the MEDIUM-confidence validation path.

    ``approve=True``  -> NIC_REVIEW (auto-validated, proceed).
    ``approve=False`` -> HUMAN_REVIEW_REQUIRED (operator re-uploads).
    """

    approve: bool
    comments: Optional[str] = None

class NICSuggestionResponse(BaseModel):
    id: UUID
    nic_code_2digit: str
    nic_code_4digit: str
    nic_code_5digit: str
    description: str
    confidence: float
    rationale: Optional[str] = None
    approved: bool

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Phase 07 — Reviewer decision schemas
# ---------------------------------------------------------------------------


class NICApproveRequest(BaseModel):
    """Phase 07 — reviewer approves the NIC selection.

    ``selected_codes`` is a non-empty list of 5-digit NIC codes. The
    reviewer should pick codes from the previously-generated suggestions
    (or paste an override they verified manually). Each code must match
    the 5-digit format (\\d{5}).

    ``justification`` is a free-form note for the audit log explaining
    *why* these codes were chosen — kept short but required.
    """

    selected_codes: list[str] = Field(..., min_length=1)
    justification: str = Field(..., min_length=1, max_length=2000)


class NICRejectRequest(BaseModel):
    """Phase 07 — reviewer rejects the NIC selection, sending the
    application back to DATA_VERIFICATION for re-classification.
    """

    justification: str = Field(..., min_length=1, max_length=2000)


class FinalReviewRequest(BaseModel):
    """Phase 07 — final reviewer signoff before portal submission.

    Body for ``POST /api/v1/applications/{id}/final-review``.
    """

    kyc_confirmed: bool
    signoff_method: str = Field(..., pattern="^(DIGITAL_SIGNATURE|AADHAAR_OTP)$")
    remarks: Optional[str] = Field(default=None, max_length=2000)


class ReviewResponse(BaseModel):
    """Generic read shape for the new review tables."""

    id: UUID
    application_id: UUID
    reviewer_id: UUID
    decided_at: Optional[datetime] = None
    declared_at: Optional[datetime] = None
    decision: Optional[str] = None
    selected_codes: Optional[list[str]] = None
    justification: Optional[str] = None
    kyc_confirmed: Optional[bool] = None
    signoff_method: Optional[str] = None
    remarks: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ExtractedDataResponse(BaseModel):
    id: UUID
    field_name: str
    field_value: Optional[str] = None
    confidence: Optional[float] = None
    validation_status: str
    bounding_box_json: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)

class AuditLogResponse(BaseModel):
    id: UUID
    actor_id: Optional[UUID] = None
    action: str
    metadata_json: Any
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BranchCreate(BaseModel):
    name: str
    code: str
    address: Optional[str] = None

class BranchResponse(BaseModel):
    id: UUID
    name: str
    code: str
    address: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
