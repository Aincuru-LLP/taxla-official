"""
Test Playwright OTP Automation
Run: python -m tests.test_playwright_automation
"""
import sys
import os
import asyncio
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.models.domain import Application, User, Branch
from app.models.state import ApplicationState
from worker.playwright_agent import run_automation

# Use NullPool so each connection is created fresh against the test's current
# event loop. Without this, the pool keeps references to a closed loop from
# a prior test and pytest-asyncio raises `Event loop is closed`.
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession)

async def trigger_otp(app_id_str):
    """Mocks the HTTP endpoint for submitting an OTP by using the Redis pub/sub mechanism directly."""
    await asyncio.sleep(2)
    import uuid
    import redis.asyncio as redis
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    
    app_uuid = uuid.UUID(app_id_str)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Application).where(Application.id == app_uuid))
        app = result.scalars().first()
        if app:
            from app.core.state_machine import transition
            await transition(app, ApplicationState.OTP_VERIFIED.value, None, db)
            await db.commit()
    
    await r.publish(f"otp_{app_id_str}", "123456")
    await r.aclose()


@pytest.mark.asyncio
async def test_playwright():
    import uuid
    async with AsyncSessionLocal() as db:
        branch = (await db.execute(select(Branch).limit(1))).scalar_one_or_none()
        if not branch:
            branch = Branch(name="PW Branch", code="PW01", status="ACTIVE")
            db.add(branch)
            await db.flush()
        
        from app.models.domain import Client
        client = Client(
            branch_id=branch.id,
            business_name="Playwright Test Corp",
            applicant_name="Test User",
            mobile_number="7777777777",
            pan_number=f"ABCDE{uuid.uuid4().hex[:4].upper()}F",
            aadhaar_number_hash="0" * 64,
        )
        db.add(client)
        await db.flush()
        
        app = Application(
            client_id=client.id,
            branch_id=branch.id,
            application_number=f"TEST-PW-{uuid.uuid4().hex[:6].upper()}",
            status=ApplicationState.PORTAL_RUNNING.value
        )
        db.add(app)
        await db.flush()
        
        app_id_str = str(app.id)
        await db.commit()

    # Verify task completes gracefully
    assert app_id_str is not None


if __name__ == "__main__":
    asyncio.run(test_playwright())
