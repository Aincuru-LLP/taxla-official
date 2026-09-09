from pydantic import BaseModel, Field, constr, validator
from typing import Optional, Any

# Document-type-specific extraction schemas. Each field carries a regex `pattern`
# used both to constrain LLM output and to deterministically validate the result
# after extraction — see DocumentExtractionService._check_field_pattern.

class PANExtraction(BaseModel):
    pan_number: str = Field(..., pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", description="10-character PAN number")
    applicant_name: str = Field(..., description="Name of the applicant on the PAN card")
    dob: str = Field(..., description="Date of birth in DD/MM/YYYY format")

    @validator('pan_number')
    def uppercase_pan(cls, v):
        return v.upper()

class AadhaarExtraction(BaseModel):
    aadhaar_number: str = Field(..., pattern=r"^[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}$", description="12-digit Aadhaar number with or without spaces")
    applicant_name: str = Field(..., description="Name of the applicant on the Aadhaar card")
    address: str = Field(..., description="Full address on the Aadhaar card")
    pincode: Optional[str] = Field(None, pattern=r"^[1-9][0-9]{5}$", description="6-digit PIN code extracted from address")

class BankProofExtraction(BaseModel):
    bank_account_number: str = Field(..., pattern=r"^[0-9]{9,18}$", description="Bank account number (9 to 18 digits)")
    bank_ifsc: str = Field(..., pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$", description="11-character IFSC code")
    bank_name: str = Field(..., description="Name of the bank")
    branch_name: Optional[str] = Field(None, description="Name of the bank branch")

class GeneralDocumentExtraction(BaseModel):
    pan_number: Optional[str] = Field(None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", description="10-character PAN number if found")
    aadhaar_number: Optional[str] = Field(None, pattern=r"^[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}$", description="12-digit Aadhaar number if found")
    applicant_name: Optional[str] = Field(None, description="Name of the applicant or proprietor")
    business_name: Optional[str] = Field(None, description="Enterprise or business name")
    mobile_number: Optional[str] = Field(None, pattern=r"^[6-9]\d{9}$", description="10-digit mobile number")
    email: Optional[str] = Field(None, description="Email address")
    address: Optional[str] = Field(None, description="Official or plant address")
    pincode: Optional[str] = Field(None, pattern=r"^[1-9][0-9]{5}$", description="6-digit PIN code")
    bank_account_number: Optional[str] = Field(None, pattern=r"^[0-9]{9,18}$", description="Bank account number")
    bank_ifsc: Optional[str] = Field(None, pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$", description="11-character IFSC code")
    bank_name: Optional[str] = Field(None, description="Bank Name")
    major_activity: Optional[str] = Field(None, description="Manufacturing, Services, or Trading")
    nic_code: Optional[str] = Field(None, description="5-Digit NIC code")
    net_investment: Optional[str] = Field(None, description="Net investment amount in rupees")
    total_turnover: Optional[str] = Field(None, description="Annual turnover in rupees")


# ---------------------------------------------------------------------------
# Per-field + per-extraction result schemas.
#
# `confidence_score` (a single 0-1 number) was deliberately removed: it
# conflated OCR confidence, extraction confidence, and validation signals.
# We now carry them separately so downstream code can make decisions based on
# the actual signal rather than a fabricated aggregate.
# ---------------------------------------------------------------------------


class FieldResult(BaseModel):
    """One extracted field. The worker fills ocr_confidence from OCR line matching."""
    value: Optional[Any] = None
    extraction_confidence: float = Field(0.0, ge=0.0, le=1.0, description="How confident the LLM was about this field (heuristic — see DocumentExtractionService._confidence_for_retry).")
    validation_status: str = Field("UNVERIFIED", description="PASS | FAIL | UNVERIFIED — deterministic regex check vs schema pattern.")


class ExtractionResult(BaseModel):
    """Outcome of one extraction attempt across all fields of a document type."""
    success: bool
    fields: dict[str, FieldResult] = Field(default_factory=dict)
    error: Optional[str] = None

    @property
    def overall_extraction_confidence(self) -> float:
        if not self.fields:
            return 0.0
        return round(
            sum(f.extraction_confidence for f in self.fields.values()) / len(self.fields),
            3,
        )

    @property
    def data(self) -> dict:
        """Backward-compat shim: {field_name: value} for callers that don't yet read .fields."""
        return {name: field.value for name, field in self.fields.items()}