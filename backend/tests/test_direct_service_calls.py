"""Direct service and router call verification test."""
import asyncio
import uuid
import pytest
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.domain import User, Branch, Application, Client, ApplicationRequirement
from app.models.state import ApplicationState
from app.services.requirement_engine import RequirementEngine
from app.services.template_service import TemplateService
from app.services.generation_service import GenerationService
from app.services.intake_service import IntakeService


async def test_full_pipeline_direct():
    print("\n--- [START] Direct Service Pipeline Test ---")
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        branch = (await db.execute(select(Branch).limit(1))).scalar_one_or_none()

        test_client = Client(
            branch_id=branch.id,
            business_name="Direct Verification Mills",
            applicant_name="Sunil Gavaskar",
            mobile_number="9811122233",
            pan_number="ABCDE1234F",
            aadhaar_number_hash="123456789012",
            gender="Male",
            social_category="General",
        )
        db.add(test_client)
        await db.flush()

        test_app = Application(
            client_id=test_client.id,
            branch_id=branch.id,
            application_number=f"VERIFY-{test_client.id.hex[:6].upper()}",
            workflow_type="NEW_UDYAM",
            status=ApplicationState.NEW.value,
        )
        db.add(test_app)
        await db.commit()
        await db.refresh(test_app)
        app_id = test_app.id
        print(f"[1] Application created: {app_id}")

        # Step 1: Initialize Requirements
        reqs = await RequirementEngine.initialize_application_requirements(app_id, db)
        assert len(reqs) == 27
        print(f"[2] Initialized {len(reqs)} standard requirements")

        # Step 2: Recalculate Completion
        pct = await RequirementEngine.recalculate_completion(app_id, db)
        print(f"[3] Initial completion percentage: {pct}%")

        # Step 3: Next Intake Question
        next_q = await IntakeService.get_next_question(app_id, db)
        assert next_q is not None
        print(f"[4] Next question retrieved: {next_q['field']} -> {next_q['question']}")

        # Step 4: Submit Answer for PAN
        ans_res = await IntakeService.process_answer(app_id, "pan", "ABCDE1234F", db)
        assert ans_res["success"] is True
        print(f"[5] Answer submitted for PAN: {ans_res}")

        # Step 5: Build Template Preview
        tmpl = await TemplateService.build_template_for_application(app_id, db)
        assert len(tmpl["sections"]) == 9
        print(f"[6] 9-section template compiled: {len(tmpl['sections'])} sections")

        # Step 6: Generate Server-side Documents (DOCX and PDF)
        pdf_doc, docx_doc = await GenerationService.generate_requirement_documents(
            application_id=app_id,
            db=db,
            user_id=user.id,
        )
        assert pdf_doc is not None
        assert docx_doc is not None
        print(f"[7] Generated documents: PDF ({pdf_doc.file_size_bytes} bytes), DOCX ({docx_doc.file_size_bytes} bytes)")

    print("\n--- [SUCCESS] ALL DIRECT SERVICE TESTS PASSED CLEANLY! ---")


if __name__ == "__main__":
    asyncio.run(test_full_pipeline_direct())
