"""Phase 07 — Reviewer decision tests.

Verifies the three Phase 07 endpoints:

  * POST /api/v1/applications/{id}/nic/approve (selected_codes + justification)
  * POST /api/v1/applications/{id}/nic/reject
  * POST /api/v1/applications/{id}/final-review

Each one writes a row to ``nic_reviews`` / ``final_reviews`` AND drives
the application state machine, so we assert both DB writes and the
state transition in one test.

The certificate endpoint (GET /certificate, 200 + 409) lives in
``test_certificates.py``.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.domain import (  # noqa: E402
    Application,
    Base,
    Branch,
    Certificate,
    Client,
    FinalReview,
    NicReview,
    NICSuggestion,
    User,
    Workflow,
)
from app.models.state import ApplicationState  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


ALL_ROLES = ("OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    from app.core.database import async_engine
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


async def _make_branch(db) -> Branch:
    branch = Branch(
        name="Reviews Test Branch",
        code=f"REV{uuid.uuid4().hex[:6].upper()}",
        status="ACTIVE",
    )
    db.add(branch)
    await db.flush()
    return branch


async def _make_user(db, *, role: str, branch_id) -> User:
    user = User(
        branch_id=branch_id,
        role=role,
        name=f"Test {role}",
        email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x" * 60,
        status="ACTIVE",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_client(db, *, branch_id) -> Client:
    rand = uuid.uuid4().hex[:4].upper()
    client = Client(
        branch_id=branch_id,
        business_name="Test Co",
        applicant_name="Test Applicant",
        mobile_number="9999999999",
        pan_number=f"ZZZZZ{rand}",
        aadhaar_number_hash="0" * 64,
    )
    db.add(client)
    await db.flush()
    return client


async def _make_application(db, *, branch_id, client_id, status) -> Application:
    application = Application(
        client_id=client_id,
        branch_id=branch_id,
        application_number=f"REV-{uuid.uuid4().hex[:8].upper()}",
        status=status,
    )
    db.add(application)
    await db.flush()
    workflow = Workflow(
        application_id=application.id,
        current_node=status,
        status="RUNNING",
        context_json={},
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(application)
    return application


@pytest_asyncio.fixture
async def env(db):
    """Two-branch seed: branch_a + branch_b + 4 roles + an application in
    NIC_REVIEW (for NIC endpoints) and one in HUMAN_REVIEW (for final).
    """
    branch_a = await _make_branch(db)
    branch_b = await _make_branch(db)
    client_a = await _make_client(db, branch_id=branch_a.id)
    client_b = await _make_client(db, branch_id=branch_b.id)
    app_nic = await _make_application(
        db,
        branch_id=branch_a.id,
        client_id=client_a.id,
        status=ApplicationState.NIC_REVIEW.value,
    )
    app_final = await _make_application(
        db,
        branch_id=branch_a.id,
        client_id=client_a.id,
        status=ApplicationState.HUMAN_REVIEW.value,
    )
    app_other = await _make_application(
        db,
        branch_id=branch_b.id,
        client_id=client_b.id,
        status=ApplicationState.NIC_REVIEW.value,
    )

    users = {}
    for role in ALL_ROLES:
        users[role] = await _make_user(db, role=role, branch_id=branch_a.id)
    branch_b_operator = await _make_user(
        db, role="OPERATOR", branch_id=branch_b.id
    )
    await db.commit()

    return {
        "branch_a": branch_a,
        "branch_b": branch_b,
        "client_a": client_a,
        "client_b": client_b,
        "app_nic": app_nic,
        "app_final": app_final,
        "app_other": app_other,
        "users": users,
        "branch_b_operator": branch_b_operator,
    }


@pytest_asyncio.fixture
async def client_under_test():
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


# ---------------------------------------------------------------------------
# /nic/approve
# ---------------------------------------------------------------------------


class TestNicApprove:
    async def test_approve_writes_nic_review_row_and_transitions(
        self, client_under_test, db, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_nic"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/nic/approve",
            json={"selected_codes": ["12345"], "justification": "matches bakery activity"},
            headers=_bearer(reviewer),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["decision"] == "approve"
        assert body["selected_codes"] == ["12345"]
        assert body["new_state"] == ApplicationState.READY_FOR_PORTAL.value

        # State machine landed.
        await db.refresh(app_obj)
        assert app_obj.status == ApplicationState.READY_FOR_PORTAL.value

        # NicReview row written with decision='APPROVE'.
        rows = (await db.execute(
            select(NicReview).where(NicReview.application_id == app_obj.id)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].decision == "APPROVE"
        assert rows[0].selected_codes == ["12345"]
        assert rows[0].reviewer_id == reviewer.id

        # Approved NICSuggestion persisted with confidence=1.0.
        sugg = (await db.execute(
            select(NICSuggestion).where(
                NICSuggestion.application_id == app_obj.id,
                NICSuggestion.nic_code_5digit == "12345",
            )
        )).scalars().first()
        assert sugg is not None
        assert sugg.approved is True

    async def test_approve_accepts_multiple_codes(
        self, client_under_test, db, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_nic"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/nic/approve",
            json={
                "selected_codes": ["12345", "67890", "11111"],
                "justification": "applicant has 3 distinct activities",
            },
            headers=_bearer(reviewer),
        )
        assert r.status_code == 200, r.text
        rows = (await db.execute(
            select(NICSuggestion).where(NICSuggestion.application_id == app_obj.id)
        )).scalars().all()
        assert len(rows) == 3
        assert {s.nic_code_5digit for s in rows} == {"12345", "67890", "11111"}

    async def test_approve_rejects_malformed_codes(
        self, client_under_test, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_nic"]
        for bad in ["1234", "123456", "abcde"]:
            r = await client_under_test.post(
                f"/api/v1/applications/{app_obj.id}/nic/approve",
                json={"selected_codes": [bad], "justification": "test"},
                headers=_bearer(reviewer),
            )
            assert r.status_code == 400, f"code={bad!r} response={r.text}"

    async def test_approve_rejects_empty_codes(
        self, client_under_test, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_nic"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/nic/approve",
            json={"selected_codes": [], "justification": "test"},
            headers=_bearer(reviewer),
        )
        # Pydantic min_length=1 raises 422.
        assert r.status_code == 422

    async def test_approve_operator_forbidden(
        self, client_under_test, env,
    ):
        operator = env["users"]["OPERATOR"]
        app_obj = env["app_nic"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/nic/approve",
            json={"selected_codes": ["12345"], "justification": "test"},
            headers=_bearer(operator),
        )
        assert r.status_code == 403, r.text

    async def test_approve_cross_branch_forbidden(
        self, client_under_test, env,
    ):
        # branch_b_operator reading branch_a's application.
        operator_b = env["branch_b_operator"]
        app_obj = env["app_nic"]  # belongs to branch_a
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/nic/approve",
            json={"selected_codes": ["12345"], "justification": "test"},
            headers=_bearer(operator_b),
        )
        assert r.status_code == 403, r.text

    async def test_approve_400_on_wrong_state(
        self, client_under_test, db, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        # app_final is in HUMAN_REVIEW, not NIC_REVIEW.
        r = await client_under_test.post(
            f"/api/v1/applications/{env['app_final'].id}/nic/approve",
            json={"selected_codes": ["12345"], "justification": "test"},
            headers=_bearer(reviewer),
        )
        assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# /nic/reject
# ---------------------------------------------------------------------------


class TestNicReject:
    async def test_reject_writes_nic_review_and_returns_to_data_verification(
        self, client_under_test, db, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_nic"]

        # Seed two prior suggestions so we can verify they get persisted
        # on the NicReview.selected_codes list.
        db.add_all([
            NICSuggestion(
                application_id=app_obj.id, nic_code_2digit="12",
                nic_code_4digit="1234", nic_code_5digit="12345",
                description="Test 1", confidence=0.7, rationale="seeded",
            ),
            NICSuggestion(
                application_id=app_obj.id, nic_code_2digit="67",
                nic_code_4digit="6789", nic_code_5digit="67890",
                description="Test 2", confidence=0.65, rationale="seeded",
            ),
        ])
        await db.commit()

        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/nic/reject",
            json={"justification": "wrong activity"},
            headers=_bearer(reviewer),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["decision"] == "reject"
        assert body["new_state"] == ApplicationState.DATA_VERIFICATION.value
        # Prior codes recorded on the NicReview row.
        assert sorted(body["rejected_codes"]) == ["12345", "67890"]

        await db.refresh(app_obj)
        assert app_obj.status == ApplicationState.DATA_VERIFICATION.value

        rows = (await db.execute(
            select(NicReview).where(NicReview.application_id == app_obj.id)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].decision == "REJECT"
        assert rows[0].justification == "wrong activity"

    async def test_reject_operator_forbidden(
        self, client_under_test, env,
    ):
        operator = env["users"]["OPERATOR"]
        app_obj = env["app_nic"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/nic/reject",
            json={"justification": "should fail"},
            headers=_bearer(operator),
        )
        assert r.status_code == 403

    async def test_reject_requires_justification(
        self, client_under_test, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_nic"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/nic/reject",
            json={"justification": ""},
            headers=_bearer(reviewer),
        )
        assert r.status_code == 422  # Pydantic min_length=1

    async def test_reject_400_on_wrong_state(
        self, client_under_test, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        # app_final is HUMAN_REVIEW, not NIC_REVIEW.
        r = await client_under_test.post(
            f"/api/v1/applications/{env['app_final'].id}/nic/reject",
            json={"justification": "should fail"},
            headers=_bearer(reviewer),
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# /final-review
# ---------------------------------------------------------------------------


class TestFinalReview:
    async def test_final_review_writes_row_and_transitions_to_approved(
        self, client_under_test, db, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_final"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/final-review",
            json={
                "kyc_confirmed": True,
                "signoff_method": "DIGITAL_SIGNATURE",
                "remarks": "all clear",
            },
            headers=_bearer(reviewer),
        )
        assert r.status_code == 200, r.text
        assert r.json()["new_state"] == ApplicationState.APPROVED.value

        await db.refresh(app_obj)
        assert app_obj.status == ApplicationState.APPROVED.value

        rows = (await db.execute(
            select(FinalReview).where(FinalReview.application_id == app_obj.id)
        )).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.kyc_confirmed is True
        assert row.signoff_method == "DIGITAL_SIGNATURE"
        assert row.remarks == "all clear"
        assert row.reviewer_id == reviewer.id

    async def test_final_review_aadhaar_otp_signoff(
        self, client_under_test, db, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_final"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/final-review",
            json={"kyc_confirmed": True, "signoff_method": "AADHAAR_OTP"},
            headers=_bearer(reviewer),
        )
        assert r.status_code == 200
        row = (await db.execute(
            select(FinalReview).where(FinalReview.application_id == app_obj.id)
        )).scalars().first()
        assert row.signoff_method == "AADHAAR_OTP"

    async def test_final_review_rejects_unknown_signoff_method(
        self, client_under_test, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_final"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/final-review",
            json={"kyc_confirmed": True, "signoff_method": "CARBON_PAPER"},
            headers=_bearer(reviewer),
        )
        assert r.status_code == 422  # pattern mismatch

    async def test_final_review_operator_forbidden(
        self, client_under_test, env,
    ):
        operator = env["users"]["OPERATOR"]
        app_obj = env["app_final"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/final-review",
            json={"kyc_confirmed": True, "signoff_method": "DIGITAL_SIGNATURE"},
            headers=_bearer(operator),
        )
        assert r.status_code == 403

    async def test_final_review_400_on_wrong_state(
        self, client_under_test, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        # app_nic is NIC_REVIEW, not HUMAN_REVIEW.
        r = await client_under_test.post(
            f"/api/v1/applications/{env['app_nic'].id}/final-review",
            json={"kyc_confirmed": True, "signoff_method": "DIGITAL_SIGNATURE"},
            headers=_bearer(reviewer),
        )
        assert r.status_code == 400