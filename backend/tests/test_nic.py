import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.domain import Application, User, Branch
from app.models.state import ApplicationState
from app.core.database import AsyncSessionLocal
from sqlalchemy import text
from app.core.security import create_access_token
from passlib.context import CryptContext

async def setup_test_data(db):
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Create test branch
    branch_id = uuid.uuid4()
    branch_code = f"TST-{str(uuid.uuid4())[:4]}"
    branch = Branch(id=branch_id, name="Test Branch", code=branch_code, status="ACTIVE")
    db.add(branch)
    
    # Create test user
    user_id = uuid.uuid4()
    rand_id = str(uuid.uuid4())[:4]
    user = User(
        id=user_id,
        email=f"test_nic_{rand_id}@taxla.com",
        password_hash=pwd_context.hash("password"),
        name="Test Operator",
        role="OPERATOR",
        branch_id=branch_id,
        status="ACTIVE"
    )
    db.add(user)
    
    from app.models.domain import Client
    
    # Create test client
    client_id = uuid.uuid4()
    client = Client(
        id=client_id,
        branch_id=branch_id,
        business_name="Test Business",
        applicant_name="Test Applicant",
        pan_number=f"ABCD{rand_id.upper()}F",
        mobile_number=f"999999{rand_id}",
        email=f"test_{rand_id}@business.com",
        aadhaar_number_hash=f"hash_{rand_id}"
    )
    db.add(client)
    
    # Create test app
    app_id = uuid.uuid4()
    application = Application(
        id=app_id,
        client_id=client_id,
        branch_id=branch_id,
        application_number=f"TEST-NIC-{rand_id}",
        status=ApplicationState.NIC_REVIEW.value,
        major_activity="Manufacturing"
    )
    db.add(application)
    
    await db.commit()
    
    token = create_access_token(str(user.id))
    return app_id, {"Authorization": f"Bearer {token}"}


async def main():
    print("[START] Running NIC Classification Integration Test...")
    
    async with AsyncSessionLocal() as db_session:
        app_id, auth_headers = await setup_test_data(db_session)
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            print(f"[1] Searching for NIC codes for app {app_id}...")
            search_payload = {
                "business_description": "Manufacture of biscuits, cakes, pastries and other bakery products",
                "location_text": "India"
            }
            response = await ac.post(f"/api/v1/applications/{app_id}/nic/search", json=search_payload, headers=auth_headers)
            
            if response.status_code != 200:
                print(f"[FAIL] NIC Search returned {response.status_code}: {response.text}")
                return
            
            data = response.json()
            if not data.get("suggestions"):
                print("[FAIL] No suggestions returned!")
                return
                
            top_suggestion = data["suggestions"][0]
            print(f"[INFO] Top Suggestion: {top_suggestion}")
            
            # Fetch the DB ID for this suggestion to approve it
            result = await db_session.execute(text(f"SELECT id FROM nic_suggestions WHERE application_id = '{app_id}' ORDER BY confidence DESC LIMIT 1"))
            db_sugg = result.fetchone()
            if not db_sugg:
                print("[FAIL] Suggestion not saved to DB")
                return
            
            suggestion_id_str = str(db_sugg[0])
            
            print(f"[2] Approving suggestion {suggestion_id_str}...")
            approve_payload = {
                "nic_suggestion_id": suggestion_id_str
            }
            response = await ac.post(f"/api/v1/applications/{app_id}/nic/approve", json=approve_payload, headers=auth_headers)
            if response.status_code != 200:
                print(f"[FAIL] NIC Approve returned {response.status_code}: {response.text}")
                return
            
            # Verify state
            result = await db_session.execute(text(f"SELECT status FROM applications WHERE id = '{app_id}'"))
            final_status = result.fetchone()[0]
            if final_status == ApplicationState.READY_FOR_PORTAL.value:
                print(f"[SUCCESS] NIC test passed! State is {final_status}")
            else:
                print(f"[FAIL] State is {final_status}, expected {ApplicationState.READY_FOR_PORTAL.value}")

if __name__ == "__main__":
    asyncio.run(main())
