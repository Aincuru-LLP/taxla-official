"""API Integration Tests for Requirements, AI Intake, and Generated Documents.
Run: .\\.venv\\Scripts\\python -m tests.test_api_intake_and_docs
"""
import asyncio
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.domain import User, Branch, Application, Client
from app.models.state import ApplicationState


async def run_e2e_intake_and_docs_test():
    print("[START] Running Requirements, AI Intake & Document Generation E2E Test...")
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        branch = (await db.execute(select(Branch).limit(1))).scalar_one_or_none()

        test_client = Client(
            branch_id=branch.id,
            business_name="API Intake Test Enterprise",
            applicant_name="Ramesh Kumar",
            mobile_number="9876543210",
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
            application_number=f"TEST-REQ-{test_client.id.hex[:6].upper()}",
            workflow_type="NEW_UDYAM",
            status=ApplicationState.NEW.value,
        )
        db.add(test_app)
        await db.commit()
        await db.refresh(test_app)
        app_id = str(test_app.id)
        user_id = str(user.id)

    token = create_access_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        print(f"[1] Testing GET /api/v1/applications/{app_id}/requirements...")
        req_res = await ac.get(f"/api/v1/applications/{app_id}/requirements", headers=headers)
        assert req_res.status_code == 200, f"Requirements failed: {req_res.text}"
        req_data = req_res.json()
        assert len(req_data["requirements"]) == 27
        print(f"    [OK] Received {len(req_data['requirements'])} requirements, completion: {req_data['completion_percentage']}%")

        print(f"[2] Testing GET /api/v1/applications/{app_id}/intake/next-question...")
        next_q_res = await ac.get(f"/api/v1/applications/{app_id}/intake/next-question", headers=headers)
        assert next_q_res.status_code == 200, f"Next question failed: {next_q_res.text}"
        q_data = next_q_res.json()
        print(f"    [OK] Question: {q_data.get('question')}")

        print(f"[3] Testing POST /api/v1/applications/{app_id}/intake/answer (Submit PAN)...")
        ans_res = await ac.post(
            f"/api/v1/applications/{app_id}/intake/answer",
            headers=headers,
            json={"field_key": "pan", "answer": "ABCDE1234F"},
        )
        assert ans_res.status_code == 200, f"Answer failed: {ans_res.text}"
        ans_data = ans_res.json()
        assert ans_data["success"] is True
        print(f"    [OK] Validated value: {ans_data['validated_value']}")

        print(f"[4] Testing GET /api/v1/applications/{app_id}/template-preview...")
        tmpl_res = await ac.get(f"/api/v1/applications/{app_id}/template-preview", headers=headers)
        assert tmpl_res.status_code == 200, f"Template preview failed: {tmpl_res.text}"
        tmpl_data = tmpl_res.json()
        assert len(tmpl_data["sections"]) == 9
        print(f"    [OK] Compiled 9-section template successfully")

        print(f"[5] Testing POST /api/v1/applications/{app_id}/requirement-documents (PDF & Word)...")
        gen_res = await ac.post(f"/api/v1/applications/{app_id}/requirement-documents", headers=headers)
        assert gen_res.status_code == 200, f"Doc generation failed: {gen_res.text}"
        gen_data = gen_res.json()
        assert gen_data["success"] is True
        assert len(gen_data["documents"]) == 2
        print(f"    [OK] Generated 2 documents: {[d['format'] for d in gen_data['documents']]}")

        print(f"[6] Testing GET /api/v1/applications/{app_id}/requirement-documents...")
        list_res = await ac.get(f"/api/v1/applications/{app_id}/requirement-documents", headers=headers)
        assert list_res.status_code == 200, f"List documents failed: {list_res.text}"
        docs_list = list_res.json()
        assert len(docs_list) >= 2
        print(f"    [OK] Retrieved {len(docs_list)} generated documents")

        print(f"[7] Testing GET download for PDF artifact...")
        pdf_id = gen_data["documents"][0]["id"]
        dl_res = await ac.get(f"/api/v1/requirement-documents/{pdf_id}/download", headers=headers)
        assert dl_res.status_code == 200, f"Download failed: {dl_res.text}"
        assert len(dl_res.content) > 100
        print(f"    [OK] Successfully downloaded PDF artifact ({len(dl_res.content)} bytes)")

        print(f"[8] Testing POST /api/v1/documents/autonomous-upload...")
        upload_files = {
            "file": ("test_requirement.pdf", dl_res.content, "application/pdf"),
        }
        auto_upload_res = await ac.post(
            "/api/v1/documents/autonomous-upload",
            files=upload_files,
            data={"application_id": app_id},
            headers=headers,
        )
        assert auto_upload_res.status_code == 200, f"Autonomous upload failed: {auto_upload_res.text}"
        auto_upload_data = auto_upload_res.json()
        assert auto_upload_data["success"] is True
        assert auto_upload_data["application_id"] == app_id
        print(f"    [OK] Autonomous upload succeeded: {auto_upload_data['message']}, execution: {auto_upload_data['execution_id']}")

    print("\n[SUCCESS] ALL REQUIREMENTS, AI INTAKE, AND DOC GENERATION TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(run_e2e_intake_and_docs_test())
