"""AI Conversational Intake Service for MSME Udyam Registration.

Uses local Ollama + Qwen to formulate natural language questions, collect answers,
validate formats, update canonical application data, and track 27 requirements.
"""
from __future__ import annotations

import datetime
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.domain import Application, ApplicationRequirement, ApplicationResponse, Client, OfficialAddress
from app.services.requirement_engine import RequirementEngine
from app.services.validators import (
    validate_pan,
    validate_aadhaar,
    validate_email,
    validate_mobile,
    validate_ifsc,
    validate_pincode,
)

logger = logging.getLogger(__name__)

# Official 27-Question Specification for Udyam MSME Intake
QUESTIONS_MAP: Dict[str, Dict[str, Any]] = {
    "aadhaar": {
        "field": "aadhaar",
        "question": "Please provide your 12-digit Aadhaar Number and confirm your consent for Udyam registration.",
        "type": "text",
        "placeholder": "e.g., 1234 5678 9012",
        "category": "IDENTITY",
        "regex": r"^[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}$",
    },
    "pan": {
        "field": "pan",
        "question": "What is the 10-character Permanent Account Number (PAN) for the business/proprietor?",
        "type": "text",
        "placeholder": "e.g., ABCDE1234F",
        "category": "IDENTITY",
        "regex": r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$",
    },
    "mobile": {
        "field": "mobile",
        "question": "What is your active 10-digit mobile number linked with your Aadhaar for OTP verification?",
        "type": "text",
        "placeholder": "e.g., 9876543210",
        "category": "IDENTITY",
        "regex": r"^[6-9]\d{9}$",
    },
    "email": {
        "field": "email",
        "question": "What is your official email address for registration notices and certificates?",
        "type": "text",
        "placeholder": "e.g., info@company.com",
        "category": "IDENTITY",
        "regex": r"^[\w\.-]+@[\w\.-]+\.\w+$",
    },
    "social_category": {
        "field": "social_category",
        "question": "What is your social category as per Government of India guidelines?",
        "type": "select",
        "options": ["General", "SC", "ST", "OBC"],
        "category": "IDENTITY",
    },
    "gender": {
        "field": "gender",
        "question": "What is the gender of the applicant / enterprise head?",
        "type": "select",
        "options": ["Male", "Female", "Other"],
        "category": "IDENTITY",
    },
    "divyang": {
        "field": "divyang",
        "question": "Is the entrepreneur specially abled (Divyang)?",
        "type": "select",
        "options": ["No", "Yes"],
        "category": "IDENTITY",
    },
    "business_name": {
        "field": "business_name",
        "question": "What is the legal name of your enterprise / business unit?",
        "type": "text",
        "placeholder": "e.g., Apex Precision Technologies",
        "category": "BUSINESS",
    },
    "official_address": {
        "field": "official_address",
        "question": "What is the registered official address of your enterprise (including PIN code, State, and District)?",
        "type": "text",
        "placeholder": "Door/Flat No., Street, City, District, State, PIN",
        "category": "ADDRESS",
    },
    "plant_units": {
        "field": "plant_units",
        "question": "Please specify your plant / factory / shop floor location names and addresses.",
        "type": "text",
        "placeholder": "e.g., Unit 1 - Industrial Estate, Gurgaon",
        "category": "ADDRESS",
    },
    "incorporation_date": {
        "field": "incorporation_date",
        "question": "What was the date of incorporation or establishment of the business?",
        "type": "date",
        "placeholder": "DD/MM/YYYY",
        "category": "BUSINESS",
    },
    "commencement_status": {
        "field": "commencement_status",
        "question": "Has your enterprise commenced commercial business operations?",
        "type": "select",
        "options": ["Yes", "No"],
        "category": "BUSINESS",
    },
    "bank_info": {
        "field": "bank_info",
        "question": "Please provide your primary business bank account details (Bank Name, Account Number, and 11-digit IFSC code).",
        "type": "text",
        "placeholder": "e.g., HDFC Bank, A/C: 50200012345678, IFSC: HDFC0001234",
        "category": "BANK",
    },
    "business_activity": {
        "field": "business_activity",
        "question": "What is the primary activity of your business? Is it Manufacturing, Services, or Trading?",
        "type": "select",
        "options": ["Manufacturing", "Services", "Trading"],
        "category": "ACTIVITY",
    },
    "nic_code": {
        "field": "nic_code",
        "question": "Please describe your exact business operations so we can assign the matching 5-digit National Industrial Classification (NIC) code.",
        "type": "text",
        "placeholder": "e.g., Custom software development and SaaS solutions",
        "category": "ACTIVITY",
    },
    "employment": {
        "field": "employment",
        "question": "How many total persons are employed in your business (Male, Female, and Other employees)?",
        "type": "text",
        "placeholder": "e.g., Male: 10, Female: 5, Other: 0",
        "category": "EMPLOYMENT",
    },
    "child_labour_declaration": {
        "field": "child_labour_declaration",
        "question": "Do you declare compliance with the Child & Adolescent Labour Prohibition and Regulation Act?",
        "type": "select",
        "options": ["Yes, I declare full compliance", "No"],
        "category": "DECLARATIONS",
    },
    "investment": {
        "field": "investment",
        "question": "What is the net investment in plant, machinery, and equipment in Rupees (after exclusions)?",
        "type": "number",
        "placeholder": "e.g., 2500000",
        "category": "FINANCIAL",
    },
    "turnover": {
        "field": "turnover",
        "question": "What was the total annual turnover of the business in the previous financial year in Rupees?",
        "type": "number",
        "placeholder": "e.g., 10000000",
        "category": "FINANCIAL",
    },
    "dic_center": {
        "field": "dic_center",
        "question": "Which District Industries Centre (DIC) office does your enterprise fall under?",
        "type": "text",
        "placeholder": "e.g., DIC Gurgaon",
        "category": "ADMINISTRATION",
    },
    "declaration": {
        "field": "declaration",
        "question": "Do you confirm all provided details are true, correct, and verified for official submission?",
        "type": "select",
        "options": ["Yes, I agree and declare", "No"],
        "category": "DECLARATIONS",
    },
    "previous_uam": {
        "field": "previous_uam",
        "question": "Do you have any previous EM-II or Udyog Aadhaar Memorandum (UAM) registration number?",
        "type": "text",
        "placeholder": "e.g., DL01A0001234 or None",
        "category": "SERVICES",
    },
    "gem_interest": {
        "field": "gem_interest",
        "question": "Would you like your enterprise to be registered on the Government e-Marketplace (GeM)?",
        "type": "select",
        "options": ["Yes", "No"],
        "category": "SERVICES",
    },
    "treds_interest": {
        "field": "treds_interest",
        "question": "Would you like your enterprise to be registered on the TReDS portal for invoice discounting?",
        "type": "select",
        "options": ["Yes", "No"],
        "category": "SERVICES",
    },
    "ncs_interest": {
        "field": "ncs_interest",
        "question": "Are you interested in registering on the National Career Service (NCS) portal?",
        "type": "select",
        "options": ["Yes", "No"],
        "category": "SERVICES",
    },
    "nsic_interest": {
        "field": "nsic_interest",
        "question": "Would you like to register on the NSIC B2B Portal for MSME procurement?",
        "type": "select",
        "options": ["Yes", "No"],
        "category": "SERVICES",
    },
    "domain_interest": {
        "field": "domain_interest",
        "question": "Would you like to claim a Free .IN Domain and official business email for your MSME?",
        "type": "select",
        "options": ["Yes", "No"],
        "category": "SERVICES",
    },
}


class IntakeService:
    """Orchestrates AI intake conversational questions and answer processing."""

    @staticmethod
    async def formulate_question_with_ollama(field_key: str, default_question: str) -> str:
        """Call Ollama Qwen to formulate a polite, conversational question for the client."""
        try:
            prompt = (
                f"You are Taxla's friendly AI intake assistant helping an Indian entrepreneur register their MSME on the official Udyam portal.\n"
                f"Field to ask: {field_key}\n"
                f"Base question: {default_question}\n\n"
                f"Rephrase this into a single, polite, professional, friendly question asking the client for this information. "
                f"Do not include quotes, markdown backticks, or any explanation. Output ONLY the rephrased question."
            )

            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3},
                    },
                )
                if res.status_code == 200:
                    text = res.json().get("response", "").strip()
                    if text and len(text) > 10:
                        return text.strip('"\'')
        except Exception as e:
            logger.warning(f"Ollama conversational phrasing unavailable, using default: {e}")

        return default_question

    @staticmethod
    async def get_next_question(application_id: uuid.UUID, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """Identify the next incomplete requirement and return the phrased question with options."""
        # Ensure requirements are initialized
        reqs_res = await db.execute(
            select(ApplicationRequirement)
            .where(ApplicationRequirement.application_id == application_id)
            .order_by(ApplicationRequirement.sort_order)
        )
        reqs = reqs_res.scalars().all()
        if not reqs:
            reqs = await RequirementEngine.initialize_application_requirements(application_id, db)

        # Find first incomplete requirement
        incomplete = [r for r in reqs if not r.is_completed]
        if not incomplete:
            return None

        target_req = incomplete[0]
        q_spec = QUESTIONS_MAP.get(target_req.requirement_key, {
            "field": target_req.requirement_key,
            "question": f"Please provide details for {target_req.display_label}.",
            "type": "text",
            "placeholder": "Enter value",
            "category": target_req.category,
        })

        friendly_text = await IntakeService.formulate_question_with_ollama(
            target_req.requirement_key,
            q_spec.get("question", target_req.display_label),
        )

        completed_count = sum(1 for r in reqs if r.is_completed)
        total_count = len(reqs)

        return {
            "requirement_key": target_req.requirement_key,
            "field": q_spec.get("field", target_req.requirement_key),
            "question": friendly_text,
            "type": q_spec.get("type", "text"),
            "options": q_spec.get("options", []),
            "placeholder": q_spec.get("placeholder", ""),
            "category": q_spec.get("category", "GENERAL"),
            "current_index": completed_count + 1,
            "total_questions": total_count,
            "progress_percentage": round((completed_count / total_count) * 100.0, 1),
        }

    @staticmethod
    def validate_answer(field_key: str, answer_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Validate format deterministically. Returns (is_valid, validated_val, error_msg)."""
        val = answer_str.strip()
        if not val:
            return False, None, "Response cannot be empty."

        if field_key == "pan":
            pan_clean = val.upper().replace(" ", "")
            if not validate_pan(pan_clean):
                return False, None, "Invalid PAN format. Must be 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)."
            return True, pan_clean, None

        elif field_key == "aadhaar":
            aadhaar_clean = re.sub(r"\s+", "", val)
            if not validate_aadhaar(aadhaar_clean):
                return False, None, "Invalid Aadhaar format. Must be exactly 12 numeric digits."
            return True, aadhaar_clean, None

        elif field_key == "mobile":
            mob_clean = re.sub(r"\D", "", val)
            if len(mob_clean) == 12 and mob_clean.startswith("91"):
                mob_clean = mob_clean[2:]
            elif len(mob_clean) == 11 and mob_clean.startswith("0"):
                mob_clean = mob_clean[1:]

            if not validate_mobile(mob_clean):
                return False, None, "Invalid mobile number. Must be a 10-digit Indian mobile number starting with 6, 7, 8, or 9."
            return True, mob_clean, None

        elif field_key == "email":
            if not validate_email(val):
                return False, None, "Invalid email address format."
            return True, val.lower(), None

        elif field_key in ["investment", "turnover"]:
            try:
                num = float(re.sub(r"[^\d.]", "", val))
                return True, str(num), None
            except ValueError:
                return False, None, "Please enter a valid numeric amount in Rupees."

        return True, val, None

    @staticmethod
    async def process_answer(
        application_id: uuid.UUID,
        field_key: str,
        answer: str,
        db: AsyncSession,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Save response, validate, update application/client fields, and recalculate."""
        is_valid, validated_val, err = IntakeService.validate_answer(field_key, answer)

        # 1. Record ApplicationResponse row
        resp = ApplicationResponse(
            application_id=application_id,
            question_key=field_key,
            raw_response=answer,
            validated_value=validated_val if is_valid else None,
            channel="AI_CHAT",
            actor_id=actor_id,
        )
        db.add(resp)

        if not is_valid:
            await db.commit()
            return {
                "success": False,
                "error": err,
                "field_key": field_key,
            }

        # 2. Update ApplicationRequirement
        req_res = await db.execute(
            select(ApplicationRequirement).where(
                ApplicationRequirement.application_id == application_id,
                ApplicationRequirement.requirement_key == field_key,
            )
        )
        req = req_res.scalars().first()
        if req:
            req.is_completed = True
            req.value = validated_val
            req.source = "USER_PROVIDED"
            req.validation_status = "VALID"
            req.validation_error = None

        # 3. Update canonical Application / Client record
        app_res = await db.execute(
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.client),
                selectinload(Application.official_address),
            )
        )
        app = app_res.scalars().first()
        if app:
            # Map into appropriate entity columns
            if field_key == "pan" and app.client:
                app.client.pan_number = validated_val
            elif field_key == "aadhaar" and app.client:
                app.client.aadhaar_number_hash = validated_val
            elif field_key == "mobile" and app.client:
                app.client.mobile_number = validated_val
            elif field_key == "email" and app.client:
                app.client.email = validated_val
            elif field_key == "gender" and app.client:
                app.client.gender = validated_val
            elif field_key == "social_category" and app.client:
                app.client.social_category = validated_val
            elif field_key == "divyang" and app.client:
                app.client.divyang_status = (validated_val.lower() == "yes")
            elif field_key == "business_name" and app.client:
                app.client.business_name = validated_val
            elif field_key == "bank_info":
                # Parse bank string if possible
                app.bank_name = validated_val
            elif field_key == "business_activity":
                app.major_activity = validated_val
            elif field_key == "investment":
                app.net_investment = float(validated_val)
            elif field_key == "turnover":
                app.total_turnover = float(validated_val)
            elif field_key == "child_labour_declaration":
                app.child_labour_declaration = ("yes" in validated_val.lower())
            elif field_key == "gem_interest":
                app.interested_in_gem = ("yes" in validated_val.lower())
            elif field_key == "treds_interest":
                app.interested_in_treds = ("yes" in validated_val.lower())
            elif field_key == "ncs_interest":
                app.interested_in_ncs = ("yes" in validated_val.lower())
            elif field_key == "nsic_interest":
                app.interested_in_nsic_b2b = ("yes" in validated_val.lower())
            elif field_key == "domain_interest":
                app.interested_in_in_domain = ("yes" in validated_val.lower())

        await db.commit()

        # 4. Recalculate completion percentage
        new_pct = await RequirementEngine.recalculate_completion(application_id, db)

        # 5. Get next question
        next_q = await IntakeService.get_next_question(application_id, db)

        return {
            "success": True,
            "field_key": field_key,
            "validated_value": validated_val,
            "completion_percentage": new_pct,
            "next_question": next_q,
            "all_completed": next_q is None,
        }
