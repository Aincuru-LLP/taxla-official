"""Unit tests for confidence separation + review decision logic.

Pure-Python tests — do not require Tesseract or Ollama.
Run: pytest backend/tests/test_confidence_logic.py -v
"""
from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.schemas.extraction import AadhaarExtraction, ExtractionResult, FieldResult, PANExtraction
from app.services.ai_extractor import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
    _check_field_pattern,
    _confidence_for_retry,
)
from app.services.review_decision_service import (
    FAIL,
    FieldSignals,
    PASS,
    REVIEW,
    ReviewDecision,
    ReviewDecisionService,
)


# ---------------------------------------------------------------------------
# _confidence_for_retry
# ---------------------------------------------------------------------------


def test_confidence_for_retry_zero_retries():
    assert _confidence_for_retry(0) == 0.90


def test_confidence_for_retry_one_retry():
    assert _confidence_for_retry(1) == 0.70


def test_confidence_for_retry_many_retries():
    assert _confidence_for_retry(2) == 0.50
    assert _confidence_for_retry(5) == 0.50


def test_confidence_for_retry_decreases_monotonically():
    """Higher retry count must never yield higher confidence."""
    confidences = [_confidence_for_retry(i) for i in range(5)]
    assert confidences == sorted(confidences, reverse=True)


# ---------------------------------------------------------------------------
# _check_field_pattern
# ---------------------------------------------------------------------------


def test_check_field_pattern_valid_pan():
    assert _check_field_pattern("pan_number", "ABCDE1234F", PANExtraction) == "PASS"


def test_check_field_pattern_invalid_pan():
    assert _check_field_pattern("pan_number", "NOT-A-PAN", PANExtraction) == "FAIL"


def test_check_field_pattern_aadhaar_with_spaces():
    assert _check_field_pattern("aadhaar_number", "1234 5678 9012", AadhaarExtraction) == "PASS"


def test_check_field_pattern_aadhaar_without_spaces():
    assert _check_field_pattern("aadhaar_number", "123456789012", AadhaarExtraction) == "PASS"


def test_check_field_pattern_aadhaar_bad_format():
    assert _check_field_pattern("aadhaar_number", "12345", AadhaarExtraction) == "FAIL"


def test_check_field_pattern_unknown_field_returns_pass():
    """Fields without a regex constraint should not be over-rejected."""
    assert _check_field_pattern("applicant_name", "Anything Goes 123", PANExtraction) == "PASS"


def test_check_field_pattern_none_value():
    """None values are treated as FAIL — a missing field is a validation fail."""
    assert _check_field_pattern("pan_number", None, PANExtraction) == "FAIL"


def test_check_field_pattern_non_string_value():
    assert _check_field_pattern("pan_number", 12345, PANExtraction) == "FAIL"


# ---------------------------------------------------------------------------
# ExtractionResult shape — separate fields, no global confidence
# ---------------------------------------------------------------------------


def test_extraction_result_carries_per_field_signals():
    """Per-field extraction_confidence + validation_status must round-trip cleanly."""
    er = ExtractionResult(
        success=True,
        fields={
            "pan_number": FieldResult(value="ABCDE1234F", extraction_confidence=0.90, validation_status="PASS"),
            "applicant_name": FieldResult(value="Test User", extraction_confidence=0.90, validation_status="PASS"),
            "dob": FieldResult(value="01/01/1990", extraction_confidence=0.70, validation_status="FAIL"),
        },
    )
    assert er.success is True
    assert "pan_number" in er.fields
    assert er.fields["pan_number"].validation_status == "PASS"
    assert er.fields["dob"].validation_status == "FAIL"


def test_extraction_result_no_global_confidence():
    """`confidence_score` must NOT exist — it was deliberately removed."""
    er = ExtractionResult(success=True)
    assert not hasattr(er, "confidence_score")


def test_extraction_result_data_property_backward_compat():
    """`.data` shim returns {field_name: value} for legacy callers."""
    er = ExtractionResult(
        success=True,
        fields={
            "pan_number": FieldResult(value="ABCDE1234F", extraction_confidence=0.90, validation_status="PASS"),
            "applicant_name": FieldResult(value="Test User", extraction_confidence=0.90, validation_status="PASS"),
        },
    )
    assert er.data == {"pan_number": "ABCDE1234F", "applicant_name": "Test User"}


def test_extraction_result_overall_extraction_confidence():
    er = ExtractionResult(
        success=True,
        fields={
            "pan_number": FieldResult(value="ABCDE1234F", extraction_confidence=0.90, validation_status="PASS"),
            "applicant_name": FieldResult(value="Test User", extraction_confidence=0.70, validation_status="PASS"),
        },
    )
    assert er.overall_extraction_confidence == 0.80  # average of 0.90 and 0.70


# ---------------------------------------------------------------------------
# ReviewDecisionService
# ---------------------------------------------------------------------------


def test_review_decision_pass_when_all_clean():
    svc = ReviewDecisionService()
    decision = svc.decide(
        FieldSignals(ocr_confidence=0.95, extraction_confidence=0.95, validation_status="PASS")
    )
    assert decision.review_decision == PASS
    assert decision.final_confidence > 0.0
    assert "All signals" in decision.rationale


def test_review_decision_review_on_low_ocr_confidence():
    svc = ReviewDecisionService()
    decision = svc.decide(
        FieldSignals(ocr_confidence=0.65, extraction_confidence=0.95, validation_status="PASS")
    )
    assert decision.review_decision == REVIEW
    assert "OCR confidence 0.65" in decision.rationale


def test_review_decision_review_on_low_extraction_confidence():
    svc = ReviewDecisionService()
    decision = svc.decide(
        FieldSignals(ocr_confidence=0.95, extraction_confidence=0.60, validation_status="PASS")
    )
    assert decision.review_decision == REVIEW
    assert "Extraction confidence 0.60" in decision.rationale


def test_review_decision_fail_on_validation_failure():
    svc = ReviewDecisionService()
    decision = svc.decide(
        FieldSignals(ocr_confidence=0.99, extraction_confidence=0.99, validation_status="FAIL")
    )
    assert decision.review_decision == FAIL
    assert decision.final_confidence == 0.0
    assert "mandatory review" in decision.rationale


def test_review_decision_fail_takes_precedence_over_review():
    """Validation FAIL must always trip FAIL even with high confidences everywhere."""
    svc = ReviewDecisionService()
    decision = svc.decide(
        FieldSignals(ocr_confidence=0.99, extraction_confidence=0.99, validation_status="FAIL")
    )
    assert decision.review_decision == FAIL


def test_review_decision_handles_missing_signals():
    """When ocr_confidence is None, the decision still works (only weights the available signals)."""
    svc = ReviewDecisionService()
    decision = svc.decide(
        FieldSignals(ocr_confidence=None, extraction_confidence=0.95, validation_status="PASS")
    )
    assert decision.review_decision == PASS


def test_review_decision_custom_thresholds():
    """Thresholds must be configurable."""
    svc = ReviewDecisionService(ocr_review_threshold=0.95, extraction_review_threshold=0.95)
    decision = svc.decide(
        FieldSignals(ocr_confidence=0.85, extraction_confidence=0.95, validation_status="PASS")
    )
    assert decision.review_decision == REVIEW
    assert "0.85 < 0.95" in decision.rationale


# ---------------------------------------------------------------------------
# Provenance constants
# ---------------------------------------------------------------------------


def test_extraction_provenance_constants_set():
    """Provenance constants must exist and be non-empty for traceability."""
    assert EXTRACTION_PROMPT_VERSION and isinstance(EXTRACTION_PROMPT_VERSION, str)
    assert EXTRACTION_SCHEMA_VERSION and isinstance(EXTRACTION_SCHEMA_VERSION, str)