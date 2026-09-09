"""
Test Document Pipeline
Run: python -m tests.test_document_pipeline
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.domain import Application, User, Branch, Document, ExtractedData
from app.models.state import ApplicationState
from app.services.ocr_service import OcrService
from worker.ocr_worker import ocr_extraction_job

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession)


def _build_synthetic_pan_card(path: str) -> None:
    """Write a real PNG containing a known PAN number to ``path``.

    Required now that the OCR worker actually runs Tesseract instead of
    reading hardcoded mock text.
    """
    from PIL import Image, ImageDraw, ImageFont

    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGB", (640, 240), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        small = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.text((20, 20), "INCOME TAX DEPARTMENT", fill="black", font=font)
    draw.text((20, 60), "GOVT OF INDIA", fill="black", font=small)
    draw.text((20, 110), "Permanent Account Number", fill="black", font=small)
    draw.text((20, 150), "ABCDE1234F", fill="black", font=font)
    draw.text((20, 200), "Name: TEST USER", fill="black", font=small)
    img.save(path, format="PNG")


async def test_pipeline():
    # Skip cleanly if the Tesseract binary isn't installed (see backend/README.md).
    if not OcrService.is_available():
        import pytest
        pytest.skip("Tesseract binary not on PATH; install per backend/README.md.")

    async with AsyncSessionLocal() as db:
        # 1. Setup mock data
        admin = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        branch = (await db.execute(select(Branch).limit(1))).scalar_one_or_none()

        import uuid
        client_id = uuid.uuid4()

        from app.models.domain import Client
        client = Client(
            branch_id=branch.id,
            business_name="Pipeline Test Corp",
            applicant_name="Test User",
            mobile_number="8888888888",
            pan_number="ABCDE1234F",
            aadhaar_number_hash="hash"
        )
        db.add(client)
        await db.flush()

        app = Application(
            client_id=client.id,
            branch_id=branch.id,
            application_number=f"TEST-DOC-{uuid.uuid4().hex[:6].upper()}",
            status=ApplicationState.DOCUMENTS_UPLOADED.value
        )
        db.add(app)
        await db.flush()

        # Create a real PNG fixture (Tesseract can't OCR raw bytes)
        os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
        test_file_path = os.path.join(settings.DOCUMENTS_DIR, "test_pan.png")
        _build_synthetic_pan_card(test_file_path)

        doc = Document(
            application_id=app.id,
            type="PAN_CARD",
            storage_path=test_file_path,
            file_name="test_pan.png",
            mime_type="image/png",
            size_bytes=os.path.getsize(test_file_path),
            ocr_status="PENDING"
        )
        db.add(doc)

        # Flush to get DB-generated UUIDs
        await db.flush()

        # Store IDs before commit to avoid lazy loading MissingGreenlet error
        app_id_str = str(app.id)
        doc_id_str = str(doc.id)
        
        await db.commit()
        
        print(f"[START] Running OCR Worker Job manually...")
        
        # 2. Run the worker job synchronously for testing
        try:
            await ocr_extraction_job(None, app_id_str, doc_id_str)
            print(f"[OK] Worker job finished without exception.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[FAIL] Worker job failed: {e}")
            
        # 3. Verify Results
        await db.refresh(app)
        print(f"App Status after extraction: {app.status}")
        
        ext_result = await db.execute(select(ExtractedData).where(ExtractedData.application_id == app.id))
        extractions = ext_result.scalars().all()
        
        print(f"Extracted {len(extractions)} fields:")
        for ext in extractions:
            print(f"  - {ext.field_name}: {ext.field_value} (conf: {ext.confidence})")
            
        if len(extractions) > 0 and app.status == ApplicationState.NIC_REVIEW.value:
            print("\n[SUCCESS] Document pipeline test passed!")
        else:
            print("\n[FAIL] Pipeline test failed.")
            
        # Cleanup
        try:
            os.remove(test_file_path)
        except OSError:
            pass

if __name__ == "__main__":
    asyncio.run(test_pipeline())
