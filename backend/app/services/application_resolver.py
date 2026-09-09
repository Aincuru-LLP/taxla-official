"""TAXLA Application & Workflow Intent Resolver.

Resolves target Application and classifies workflow intent from uploaded documents,
metadata, embedded barcodes/QR references, and extracted identity signals.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Application, Client, User
from app.models.state import ApplicationState

logger = logging.getLogger("taxla.services.resolver")


class WorkflowIntent(str, Enum):
    NEW_UDYAM = "NEW_UDYAM"
    UDYAMI_LOGIN = "UDYAMI_LOGIN"
    UDYAM_UPDATE = "UDYAM_UPDATE"
    UDYAM_CANCEL = "UDYAM_CANCEL"
    PRINT_CERTIFICATE = "PRINT_CERTIFICATE"
    VERIFY_UDYAM = "VERIFY_UDYAM"
    VERIFY_UAM = "VERIFY_UAM"
    FORGOT_NUMBER = "FORGOT_NUMBER"
    UAM_MIGRATION = "UAM_MIGRATION"
    ASSISTED_UAM_MIGRATION = "ASSISTED_UAM_MIGRATION"
    SUPPORTING_DOCUMENT = "SUPPORTING_DOCUMENT"
    UNKNOWN = "UNKNOWN"


@dataclass
class ResolutionResult:
    application_id: Optional[uuid.UUID]
    client_id: Optional[uuid.UUID]
    workflow_type: str
    confidence: float
    resolution_method: str
    is_ambiguous: bool
    is_new_application_created: bool
    candidate_application_ids: List[uuid.UUID]
    details: Dict[str, Any]


class ApplicationResolver:
    """Deterministically identifies the target Application and Client for an uploaded document."""

    @staticmethod
    def extract_embedded_references(raw_text: str) -> Dict[str, Optional[str]]:
        """Extracts embedded identifiers like UUID, Taxla ref (TX-XXXX), PAN, Mobile from text."""
        result = {
            "application_uuid": None,
            "application_number": None,
            "pan_number": None,
            "mobile_number": None,
            "udyam_number": None,
            "uam_number": None,
        }
        if not raw_text:
            return result

        # 1. Embedded UUID (36 chars)
        uuid_pattern = r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
        uuid_matches = re.findall(uuid_pattern, raw_text, re.IGNORECASE)
        if uuid_matches:
            result["application_uuid"] = uuid_matches[0]

        # 2. Taxla Reference: TX-XXXXX
        tx_match = re.search(r"\bTX-[A-Z0-9]{4,12}\b", raw_text, re.IGNORECASE)
        if tx_match:
            result["application_number"] = tx_match.group(0).upper()

        # 3. PAN: 5 letters, 4 digits, 1 letter
        pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", raw_text)
        if pan_match:
            result["pan_number"] = pan_match.group(0)

        # 4. Mobile Number: 10 digits starting with 6-9
        mobile_match = re.search(r"\b[6-9][0-9]{9}\b", raw_text)
        if mobile_match:
            result["mobile_number"] = mobile_match.group(0)

        # 5. Udyam Registration Number: UDYAM-XX-00-0000000
        udyam_match = re.search(r"\bUDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}\b", raw_text, re.IGNORECASE)
        if udyam_match:
            result["udyam_number"] = udyam_match.group(0).upper()

        # 6. UAM Number: XX00A0000000
        uam_match = re.search(r"\b[A-Z]{2}[0-9]{2}[A-Z]{1}[0-9]{7}\b", raw_text, re.IGNORECASE)
        if uam_match:
            result["uam_number"] = uam_match.group(0).upper()

        return result

    @classmethod
    async def resolve(
        cls,
        raw_text: str,
        filename: str,
        branch_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        db: AsyncSession,
        extracted_data: Optional[Dict[str, Any]] = None,
        explicit_app_id: Optional[uuid.UUID] = None,
        auto_create: bool = True,
    ) -> ResolutionResult:
        """Resolves target Application with confidence and ambiguity tracking."""
        # 1. Explicit Application ID provided by operator
        if explicit_app_id:
            app_stmt = select(Application).where(Application.id == explicit_app_id)
            app_res = await db.execute(app_stmt)
            app = app_res.scalar_one_or_none()
            if app:
                intent = WorkflowIntentResolver.classify(raw_text, filename, extracted_data)
                return ResolutionResult(
                    application_id=app.id,
                    client_id=app.client_id,
                    workflow_type=app.workflow_type or intent.value,
                    confidence=1.0,
                    resolution_method="EXPLICIT_PARAMETER",
                    is_ambiguous=False,
                    is_new_application_created=False,
                    candidate_application_ids=[app.id],
                    details={"source": "explicit_id"},
                )

        extracted_refs = cls.extract_embedded_references(raw_text)
        pan = (extracted_data or {}).get("pan_number") or extracted_refs["pan_number"]
        mobile = (extracted_data or {}).get("mobile_number") or extracted_refs["mobile_number"]
        app_uuid_str = extracted_refs["application_uuid"]
        app_num = extracted_refs["application_number"]

        # 2. Match by embedded UUID
        if app_uuid_str:
            try:
                target_uuid = uuid.UUID(app_uuid_str)
                stmt = select(Application).where(Application.id == target_uuid, Application.branch_id == branch_id)
                res = await db.execute(stmt)
                app = res.scalar_one_or_none()
                if app:
                    return ResolutionResult(
                        application_id=app.id,
                        client_id=app.client_id,
                        workflow_type=app.workflow_type or WorkflowIntent.NEW_UDYAM.value,
                        confidence=0.99,
                        resolution_method="EMBEDDED_UUID",
                        is_ambiguous=False,
                        is_new_application_created=False,
                        candidate_application_ids=[app.id],
                        details={"embedded_uuid": app_uuid_str},
                    )
            except Exception:
                pass

        # 3. Match by Application Number (TX-XXXXX)
        if app_num:
            stmt = select(Application).where(
                Application.application_number == app_num, Application.branch_id == branch_id
            )
            res = await db.execute(stmt)
            app = res.scalar_one_or_none()
            if app:
                return ResolutionResult(
                    application_id=app.id,
                    client_id=app.client_id,
                    workflow_type=app.workflow_type or WorkflowIntent.NEW_UDYAM.value,
                    confidence=0.95,
                    resolution_method="APPLICATION_NUMBER",
                    is_ambiguous=False,
                    is_new_application_created=False,
                    candidate_application_ids=[app.id],
                    details={"application_number": app_num},
                )

        # 4. Match by Client PAN / Mobile
        if pan:
            client_stmt = select(Client).where(Client.pan_number == pan, Client.branch_id == branch_id)
            client_res = await db.execute(client_stmt)
            clients = client_res.scalars().all()
            if clients:
                matched_client = clients[0]
                # Find active application for this client
                app_stmt = (
                    select(Application)
                    .where(Application.client_id == matched_client.id)
                    .order_by(Application.created_at.desc())
                )
                app_res = await db.execute(app_stmt)
                apps = app_res.scalars().all()
                if len(apps) == 1:
                    return ResolutionResult(
                        application_id=apps[0].id,
                        client_id=matched_client.id,
                        workflow_type=apps[0].workflow_type or WorkflowIntent.NEW_UDYAM.value,
                        confidence=0.90,
                        resolution_method="CLIENT_PAN_MATCH",
                        is_ambiguous=False,
                        is_new_application_created=False,
                        candidate_application_ids=[apps[0].id],
                        details={"pan": pan, "matched_client": str(matched_client.id)},
                    )
                elif len(apps) > 1:
                    # Multiple applications found for client -> Ambiguous
                    return ResolutionResult(
                        application_id=apps[0].id,
                        client_id=matched_client.id,
                        workflow_type=apps[0].workflow_type or WorkflowIntent.NEW_UDYAM.value,
                        confidence=0.60,
                        resolution_method="CLIENT_PAN_AMBIGUOUS",
                        is_ambiguous=True,
                        is_new_application_created=False,
                        candidate_application_ids=[a.id for a in apps],
                        details={"pan": pan, "candidate_count": len(apps)},
                    )

        # 5. Create new Application & Client if auto_create is True
        intent = WorkflowIntentResolver.classify(raw_text, filename, extracted_data)
        if auto_create:
            business_name = (extracted_data or {}).get("enterprise_name") or f"New Enterprise {uuid.uuid4().hex[:6].upper()}"
            applicant_name = (extracted_data or {}).get("applicant_name") or "Applicant"
            client_pan = pan or f"ABCDE{uuid.uuid4().hex[:4].upper()}F"

            new_client = Client(
                id=uuid.uuid4(),
                branch_id=branch_id,
                business_name=business_name,
                applicant_name=applicant_name,
                mobile_number=mobile or "9876543210",
                pan_number=client_pan,
                aadhaar_number_hash="0" * 64,
            )
            db.add(new_client)
            await db.flush()

            new_app = Application(
                id=uuid.uuid4(),
                client_id=new_client.id,
                branch_id=branch_id,
                application_number=f"TX-{uuid.uuid4().hex[:6].upper()}",
                workflow_type=intent.value if intent != WorkflowIntent.UNKNOWN else WorkflowIntent.NEW_UDYAM.value,
                status=ApplicationState.NEW.value,
                assigned_to=user_id,
            )
            db.add(new_app)
            await db.flush()

            logger.info("Auto-created Client %s and Application %s", new_client.id, new_app.id)

            return ResolutionResult(
                application_id=new_app.id,
                client_id=new_client.id,
                workflow_type=new_app.workflow_type,
                confidence=0.85,
                resolution_method="AUTO_CREATED_NEW",
                is_ambiguous=False,
                is_new_application_created=True,
                candidate_application_ids=[new_app.id],
                details={"reason": "no_prior_match_auto_created"},
            )

        return ResolutionResult(
            application_id=None,
            client_id=None,
            workflow_type=intent.value,
            confidence=0.0,
            resolution_method="UNRESOLVED",
            is_ambiguous=False,
            is_new_application_created=False,
            candidate_application_ids=[],
            details={"reason": "auto_create_disabled_no_match"},
        )


class WorkflowIntentResolver:
    """Classifies document workflow intent from filename, keywords, and extracted fields."""

    @staticmethod
    def classify(
        raw_text: str,
        filename: str = "",
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> WorkflowIntent:
        text_lower = (raw_text or "").lower()
        file_lower = (filename or "").lower()

        # Check for Migration
        if "uam migration" in text_lower or "assisted migration" in text_lower or "migrate uam" in file_lower:
            if "assisted" in text_lower:
                return WorkflowIntent.ASSISTED_UAM_MIGRATION
            return WorkflowIntent.UAM_MIGRATION

        # Check for Udyam Cancellation
        if "cancellation" in text_lower or "cancel udyam" in text_lower or "cancel" in file_lower:
            return WorkflowIntent.UDYAM_CANCEL

        # Check for Udyam Update
        if "update udyam" in text_lower or "edit registration" in text_lower or "amendment" in text_lower:
            return WorkflowIntent.UDYAM_UPDATE

        # Check for Certificate Verification or Print
        if "certificate" in text_lower or "print certificate" in text_lower or "certificate" in file_lower:
            return WorkflowIntent.PRINT_CERTIFICATE

        # Check for Forgot Number
        if "forgot udyam" in text_lower or "forgot uam" in text_lower:
            return WorkflowIntent.FORGOT_NUMBER

        # Check for Udyam Registration (New)
        if (
            "udyam registration" in text_lower
            or "msme registration" in text_lower
            or "requirement" in file_lower
            or "enterprise" in text_lower
            or "applicant" in text_lower
        ):
            return WorkflowIntent.NEW_UDYAM

        # Check supporting single-identity docs
        if "income tax department" in text_lower or "permanent account number" in text_lower:
            return WorkflowIntent.SUPPORTING_DOCUMENT
        if "unique identification authority of india" in text_lower or "aadhaar" in text_lower:
            return WorkflowIntent.SUPPORTING_DOCUMENT

        return WorkflowIntent.NEW_UDYAM
