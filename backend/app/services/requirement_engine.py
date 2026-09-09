"""Requirement Engine for Indian MSME Udyam Registration.

Implements the official 27-item requirement specification, 2026 MSME classification
thresholds, automatic requirement matching from extracted documents, and completion
scoring.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Application, ApplicationRequirement, ExtractedData

logger = logging.getLogger(__name__)

# Updated 2026 Government of India MSME Classification Thresholds (effective from 1 April 2025/2026)
INVESTMENT_LIMITS = {
    "MICRO": 25000000.0,       # ₹2.5 Crore
    "SMALL": 250000000.0,      # ₹25 Crore
    "MEDIUM": 1250000000.0,    # ₹125 Crore
}

TURNOVER_LIMITS = {
    "MICRO": 100000000.0,      # ₹10 Crore
    "SMALL": 1000000000.0,     # ₹100 Crore
    "MEDIUM": 5000000000.0,    # ₹500 Crore
}

STANDARD_27_REQUIREMENTS: List[Dict[str, Any]] = [
    {"key": "aadhaar", "label": "1. Aadhaar Number & Name (Role-Based Consent)", "category": "IDENTITY", "required": True},
    {"key": "pan", "label": "2. Business / Proprietor PAN", "category": "IDENTITY", "required": True},
    {"key": "mobile", "label": "3. Primary Mobile Number (OTP Linked)", "category": "IDENTITY", "required": True},
    {"key": "email", "label": "4. Official Email Address", "category": "IDENTITY", "required": True},
    {"key": "social_category", "label": "5. Social Category (General/SC/ST/OBC)", "category": "IDENTITY", "required": True},
    {"key": "gender", "label": "6. Entrepreneur Gender", "category": "IDENTITY", "required": True},
    {"key": "divyang", "label": "7. Specially Abled / Divyang Status", "category": "IDENTITY", "required": True},
    {"key": "business_name", "label": "8. Enterprise / Business Name", "category": "BUSINESS", "required": True},
    {"key": "official_address", "label": "9. Official Plant / Registered Address", "category": "ADDRESS", "required": True},
    {"key": "plant_units", "label": "10. Plant / Unit Locations (Add Units)", "category": "ADDRESS", "required": True},
    {"key": "incorporation_date", "label": "11. Date of Incorporation / Registration", "category": "BUSINESS", "required": True},
    {"key": "commencement_status", "label": "12. Business Commencement Status & Date", "category": "BUSINESS", "required": True},
    {"key": "bank_info", "label": "13. Bank Name, Account Number & IFSC", "category": "BANK", "required": True},
    {"key": "business_activity", "label": "14. Major Activity (Manufacturing / Services / Trading)", "category": "ACTIVITY", "required": True},
    {"key": "nic_code", "label": "15. 5-Digit NIC Activity Codes (Multiple Supported)", "category": "ACTIVITY", "required": True},
    {"key": "employment", "label": "16. Employment Details (Male/Female/Other)", "category": "EMPLOYMENT", "required": True},
    {"key": "child_labour_declaration", "label": "17. Child & Adolescent Labour Prohibition Declaration", "category": "DECLARATIONS", "required": True},
    {"key": "investment", "label": "18. Net Investment in Plant/Machinery (₹)", "category": "FINANCIAL", "required": True},
    {"key": "turnover", "label": "19. Net Annual Turnover (₹)", "category": "FINANCIAL", "required": True},
    {"key": "dic_center", "label": "20. District Industries Centre (DIC) Selection", "category": "ADMINISTRATION", "required": True},
    {"key": "declaration", "label": "21. Self Declaration & Final Aadhaar OTP Verification", "category": "DECLARATIONS", "required": True},
    {"key": "previous_uam", "label": "22. Previous EM-II / UAM Registration Number", "category": "SERVICES", "required": False},
    {"key": "gem_interest", "label": "23. GeM Portal Registration Interest", "category": "SERVICES", "required": False},
    {"key": "treds_interest", "label": "24. TReDS Portal Registration Interest", "category": "SERVICES", "required": False},
    {"key": "ncs_interest", "label": "25. NCS Portal Registration Interest", "category": "SERVICES", "required": False},
    {"key": "nsic_interest", "label": "26. NSIC B2B Portal Interest", "category": "SERVICES", "required": False},
    {"key": "domain_interest", "label": "27. Free .IN Domain & Business Email Preference", "category": "SERVICES", "required": False},
]

# Field alias mapping from document extraction keys to canonical requirement keys
FIELD_ALIAS_MAP: Dict[str, str] = {
    "aadhaar_number": "aadhaar",
    "aadhaar": "aadhaar",
    "pan_number": "pan",
    "pan": "pan",
    "mobile_number": "mobile",
    "mobile": "mobile",
    "email": "email",
    "business_name": "business_name",
    "applicant_name": "aadhaar",  # Maps to identity requirement
    "address": "official_address",
    "official_address": "official_address",
    "bank_account_number": "bank_info",
    "bank_ifsc": "bank_info",
    "bank_name": "bank_info",
    "bank_info": "bank_info",
    "major_activity": "business_activity",
    "business_activity": "business_activity",
    "nic_code": "nic_code",
    "nic_5digit": "nic_code",
    "net_investment": "investment",
    "investment": "investment",
    "total_turnover": "turnover",
    "turnover": "turnover",
    "male_employees": "employment",
    "female_employees": "employment",
    "other_employees": "employment",
    "child_labour_declaration": "child_labour_declaration",
}


class RequirementEngine:
    """Calculates missing requirements, performs auto-matching, and classifies MSME."""

    @staticmethod
    def get_default_requirements() -> List[Dict[str, Any]]:
        return STANDARD_27_REQUIREMENTS

    @staticmethod
    async def initialize_application_requirements(
        application_id: uuid.UUID,
        db: AsyncSession,
        org_type: str = "Proprietorship",
    ) -> List[ApplicationRequirement]:
        """Ensure all 27 standard requirements exist for the application."""
        existing_res = await db.execute(
            select(ApplicationRequirement).where(ApplicationRequirement.application_id == application_id)
        )
        existing = existing_res.scalars().all()
        if existing:
            return list(existing)

        created: List[ApplicationRequirement] = []
        for idx, item in enumerate(STANDARD_27_REQUIREMENTS):
            req = ApplicationRequirement(
                application_id=application_id,
                requirement_key=item["key"],
                display_label=item["label"],
                category=item.get("category", "GENERAL"),
                is_required=item["required"],
                is_completed=False,
                sort_order=idx + 1,
            )
            db.add(req)
            created.append(req)

        await db.commit()
        return created

    @staticmethod
    async def recalculate_completion(application_id: uuid.UUID, db: AsyncSession) -> float:
        """Recalculate application completion percentage based on required fields."""
        app_res = await db.execute(select(Application).where(Application.id == application_id))
        app = app_res.scalars().first()
        if not app:
            return 0.0

        reqs_res = await db.execute(
            select(ApplicationRequirement).where(ApplicationRequirement.application_id == application_id)
        )
        reqs = reqs_res.scalars().all()

        if not reqs:
            # Auto-initialize if missing
            reqs = await RequirementEngine.initialize_application_requirements(application_id, db)

        mandatory_reqs = [r for r in reqs if r.is_required]
        if not mandatory_reqs:
            return 100.0

        completed_mandatory = sum(1 for r in mandatory_reqs if r.is_completed)
        pct = round((completed_mandatory / len(mandatory_reqs)) * 100.0, 1)

        app.completion_percentage = pct
        await db.commit()
        return float(pct)

    @staticmethod
    async def match_extracted_fields(
        application_id: uuid.UUID,
        extracted_data: Dict[str, Any],
        doc_id: Optional[uuid.UUID],
        db: AsyncSession,
    ) -> int:
        """Auto-match extracted fields against application requirements."""
        matched_count = 0
        reqs_res = await db.execute(
            select(ApplicationRequirement).where(ApplicationRequirement.application_id == application_id)
        )
        reqs = {r.requirement_key: r for r in reqs_res.scalars().all()}

        if not reqs:
            await RequirementEngine.initialize_application_requirements(application_id, db)
            reqs_res = await db.execute(
                select(ApplicationRequirement).where(ApplicationRequirement.application_id == application_id)
            )
            reqs = {r.requirement_key: r for r in reqs_res.scalars().all()}

        for raw_key, raw_val in extracted_data.items():
            if raw_val is None or (isinstance(raw_val, str) and not raw_val.strip()):
                continue

            req_key = FIELD_ALIAS_MAP.get(raw_key, raw_key)
            req = reqs.get(req_key)
            if req:
                req.is_completed = True
                req.value = str(raw_val).strip()
                req.source = "DOCUMENT_EXTRACTED"
                req.source_document_id = doc_id
                req.validation_status = "VALID"
                req.validation_error = None
                matched_count += 1

        await db.commit()
        await RequirementEngine.recalculate_completion(application_id, db)
        return matched_count

    @staticmethod
    def calculate_msme_category(investment: float, turnover: float) -> str:
        """Classify enterprise according to official 2026 MSME thresholds."""
        if investment <= INVESTMENT_LIMITS["MICRO"] and turnover <= TURNOVER_LIMITS["MICRO"]:
            return "MICRO"
        elif investment <= INVESTMENT_LIMITS["SMALL"] and turnover <= TURNOVER_LIMITS["SMALL"]:
            return "SMALL"
        elif investment <= INVESTMENT_LIMITS["MEDIUM"] and turnover <= TURNOVER_LIMITS["MEDIUM"]:
            return "MEDIUM"
        else:
            return "LARGE / EXCEEDS_MSME_LIMITS"
