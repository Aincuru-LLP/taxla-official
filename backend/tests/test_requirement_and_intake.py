"""Tests for RequirementEngine, 2026 MSME Limits, TemplateService, GenerationService, and IntakeService."""
import os
import uuid
import pytest
import pytest_asyncio
from app.services.requirement_engine import RequirementEngine, INVESTMENT_LIMITS, TURNOVER_LIMITS, STANDARD_27_REQUIREMENTS
from app.services.template_service import TemplateService
from app.services.generation_service import GenerationService
from app.services.intake_service import IntakeService, QUESTIONS_MAP


def test_2026_msme_thresholds():
    """Verify 2026 MSME classification thresholds."""
    assert RequirementEngine.calculate_msme_category(20000000.0, 80000000.0) == "MICRO"
    assert RequirementEngine.calculate_msme_category(250000000.0, 900000000.0) == "SMALL"
    assert RequirementEngine.calculate_msme_category(1000000000.0, 4000000000.0) == "MEDIUM"
    assert RequirementEngine.calculate_msme_category(2000000000.0, 6000000000.0) == "LARGE / EXCEEDS_MSME_LIMITS"


def test_standard_27_requirements_definition():
    """Verify all 27 requirements are defined with labels, keys, and categories."""
    assert len(STANDARD_27_REQUIREMENTS) == 27
    keys = [r["key"] for r in STANDARD_27_REQUIREMENTS]
    assert "aadhaar" in keys
    assert "pan" in keys
    assert "mobile" in keys
    assert "email" in keys
    assert "nic_code" in keys
    assert "investment" in keys
    assert "turnover" in keys


def test_template_service_structure():
    """Verify 9-section template generation and prefilling."""
    template = TemplateService.generate_intake_template_structure(
        template_name="Test Enterprise Template",
        business_type="Software Services",
        org_type="Private Limited",
        prefilled_data={
            "pan": "ABCDE1234F",
            "business_name": "Test Tech Pvt Ltd",
            "mobile": "9876543210",
        },
    )
    assert len(template["sections"]) == 9
    sec1 = template["sections"][0]
    assert sec1["section_id"] == "identity"
    sec2 = template["sections"][1]
    assert sec2["section_id"] == "business"
    
    # Check prefilled values
    pan_field = next(f for f in sec2["fields"] if f["key"] == "pan")
    assert pan_field["value"] == "ABCDE1234F"


def test_generation_service_docx_and_pdf(tmp_path):
    """Verify DOCX and PDF files are generated without error."""
    template = TemplateService.generate_intake_template_structure(
        template_name="Acme Corp Intake",
        business_type="Manufacturing",
        org_type="Partnership",
    )
    docx_file = str(tmp_path / "test_intake.docx")
    pdf_file = str(tmp_path / "test_intake.pdf")

    GenerationService.generate_docx(template, docx_file)
    assert os.path.exists(docx_file)
    assert os.path.getsize(docx_file) > 1000

    GenerationService.generate_pdf(template, pdf_file)
    assert os.path.exists(pdf_file)
    assert os.path.getsize(pdf_file) > 1000


def test_intake_answer_validation():
    """Verify deterministic validation for PAN, Aadhaar, Mobile, Email, and Amounts."""
    # PAN
    ok, val, err = IntakeService.validate_answer("pan", "abcde1234f")
    assert ok is True
    assert val == "ABCDE1234F"

    ok, val, err = IntakeService.validate_answer("pan", "INVALID_PAN")
    assert ok is False
    assert "Invalid PAN format" in err

    # Aadhaar
    ok, val, err = IntakeService.validate_answer("aadhaar", "1234 5678 9012")
    assert ok is True
    assert val == "123456789012"

    ok, val, err = IntakeService.validate_answer("aadhaar", "1234")
    assert ok is False

    # Mobile
    ok, val, err = IntakeService.validate_answer("mobile", "+91 9876543210")
    assert ok is True
    assert val == "9876543210"

    ok, val, err = IntakeService.validate_answer("mobile", "12345")
    assert ok is False

    # Email
    ok, val, err = IntakeService.validate_answer("email", "info@example.com")
    assert ok is True
    assert val == "info@example.com"

    ok, val, err = IntakeService.validate_answer("email", "not-an-email")
    assert ok is False
