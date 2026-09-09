"""Tests for ApplicationResolver and WorkflowIntentResolver."""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.domain import Application, Branch, Client, User
from app.models.state import ApplicationState
from app.services.application_resolver import ApplicationResolver, WorkflowIntent, WorkflowIntentResolver


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.mark.asyncio
async def test_extract_embedded_references():
    sample_text = (
        "TAXLA REQUIREMENT FORM\n"
        "Reference: TX-AB12CD\n"
        "Client PAN: ABCDE1234F\n"
        "Mobile: 9876543210\n"
        "Udyam No: UDYAM-MH-12-0012345\n"
        "UUID: 12345678-1234-5678-1234-567812345678\n"
    )
    refs = ApplicationResolver.extract_embedded_references(sample_text)
    assert refs["application_number"] == "TX-AB12CD"
    assert refs["pan_number"] == "ABCDE1234F"
    assert refs["mobile_number"] == "9876543210"
    assert refs["udyam_number"] == "UDYAM-MH-12-0012345"
    assert refs["application_uuid"] == "12345678-1234-5678-1234-567812345678"


@pytest.mark.asyncio
async def test_workflow_intent_classification():
    assert WorkflowIntentResolver.classify("UAM Migration Form", "migration.pdf") == WorkflowIntent.UAM_MIGRATION
    assert WorkflowIntentResolver.classify("Assisted UAM Migration", "assist.pdf") == WorkflowIntent.ASSISTED_UAM_MIGRATION
    assert WorkflowIntentResolver.classify("Request for Udyam Cancellation", "cancel.pdf") == WorkflowIntent.UDYAM_CANCEL
    assert WorkflowIntentResolver.classify("Udyam Update and Amendment", "update.pdf") == WorkflowIntent.UDYAM_UPDATE
    assert WorkflowIntentResolver.classify("Print Official Udyam Certificate", "cert.pdf") == WorkflowIntent.PRINT_CERTIFICATE
    assert WorkflowIntentResolver.classify("Forgot Udyam / UAM Number Retrieval", "forgot.pdf") == WorkflowIntent.FORGOT_NUMBER
    assert WorkflowIntentResolver.classify("New Udyam Registration Requirement Form", "form.pdf") == WorkflowIntent.NEW_UDYAM


@pytest.mark.asyncio
async def test_application_resolver_matches_existing_app_by_pan(db: AsyncSession):
    branch = Branch(name="Resolver Branch", code=f"RB{uuid.uuid4().hex[:6].upper()}", status="ACTIVE")
    db.add(branch)
    await db.flush()

    user = User(
        email=f"operator_{uuid.uuid4().hex[:6]}@taxla.in",
        name="Operator",
        password_hash="hash",
        role="OPERATOR",
        branch_id=branch.id,
        status="ACTIVE",
    )
    db.add(user)
    await db.flush()

    import random
    pan_digits = f"{random.randint(1000, 9999)}"
    client = Client(
        branch_id=branch.id,
        business_name="Resolved Tech Pvt Ltd",
        applicant_name="Rohan Verma",
        mobile_number="9876543210",
        pan_number=f"ABCDE{pan_digits}F",
        aadhaar_number_hash="0" * 64,
    )
    db.add(client)
    await db.flush()

    app = Application(
        client_id=client.id,
        branch_id=branch.id,
        application_number=f"TX-{uuid.uuid4().hex[:6].upper()}",
        workflow_type="NEW_UDYAM",
        status=ApplicationState.NEW.value,
    )
    db.add(app)
    await db.commit()

    # Simulate raw text containing client's PAN
    doc_text = f"Applicant Details\nPAN: {client.pan_number}\nBusiness Name: Resolved Tech Pvt Ltd"
    res = await ApplicationResolver.resolve(
        raw_text=doc_text,
        filename="requirement.pdf",
        branch_id=branch.id,
        user_id=user.id,
        db=db,
    )

    assert res.application_id == app.id
    assert res.client_id == client.id
    assert res.resolution_method == "CLIENT_PAN_MATCH"
    assert res.confidence >= 0.9
    assert res.is_ambiguous is False
