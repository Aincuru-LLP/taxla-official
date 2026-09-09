"""Phase 05 — Role Enforcement + Branch-Scope Guards integration tests.

Verifies the matrix from ``documents/04_user_roles_and_permissions.md``:

  * Endpoint X allowed role -> 200/202/201 (happy path).
  * Endpoint X forbidden role -> 403.
  * Cross-branch access -> 403, even with an allowed role.

Uses ``httpx.AsyncClient`` against the FastAPI app defined in
``app.main``. ``User`` rows are seeded with bcrypt-hashed passwords
(though the tests mint JWTs directly so the password is never exercised).

Run: pytest backend/tests/test_rbac.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402 — the FastAPI instance under test
from app.models.domain import (  # noqa: E402
    Application,
    Branch,
    Client,
    User,
    Workflow,
)
from app.models.domain import Base  # noqa: E402
from app.models.state import ApplicationState  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Idempotent table creation (mirrors other test files)."""
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


# Roles we exercise in this matrix — matches seeded users in scripts/seed_data.py.
ALL_ROLES = ("OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN")


async def _make_user(db, *, role: str, branch_id: Optional[uuid.UUID]) -> User:
    user = User(
        branch_id=branch_id,
        role=role,
        name=f"Test {role}",
        email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x" * 60,  # bcrypt-shaped dummy; tests mint JWTs directly
        status="ACTIVE",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_branch(db, *, code: Optional[str] = None) -> Branch:
    branch = Branch(
        name="Test Branch",
        code=code or f"B{uuid.uuid4().hex[:8].upper()}",
        status="ACTIVE",
    )
    db.add(branch)
    await db.flush()
    return branch


async def _make_client(db, *, branch_id: uuid.UUID) -> Client:
    rand = uuid.uuid4().hex[:4].upper()
    client = Client(
        branch_id=branch_id,
        business_name="Test Co",
        applicant_name="Test Applicant",
        mobile_number="9999999999",
        pan_number=f"ABCDE{rand}",
        aadhaar_number_hash="0" * 64,
    )
    db.add(client)
    await db.flush()
    return client


async def _make_application(
    db,
    *,
    branch_id: uuid.UUID,
    client_id: uuid.UUID,
    status: str = ApplicationState.NEW.value,
) -> Application:
    application = Application(
        client_id=client_id,
        branch_id=branch_id,
        application_number=f"RBAC-{uuid.uuid4().hex[:8].upper()}",
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


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest_asyncio.fixture
async def branches_users_apps(db):
    """Seed: branch_a, branch_b, + 4 users (one per role) in branch_a.

    Returns a dict so individual tests can pull what they need.
    Cross-branch tests add a branch_b user on demand.
    """
    branch_a = await _make_branch(db, code=f"A{uuid.uuid4().hex[:6].upper()}")
    branch_b = await _make_branch(db, code=f"B{uuid.uuid4().hex[:6].upper()}")
    client_a = await _make_client(db, branch_id=branch_a.id)
    client_b = await _make_client(db, branch_id=branch_b.id)
    app_a = await _make_application(db, branch_id=branch_a.id, client_id=client_a.id)
    app_b = await _make_application(db, branch_id=branch_b.id, client_id=client_b.id)

    users_by_role = {}
    for role in ALL_ROLES:
        users_by_role[role] = await _make_user(db, role=role, branch_id=branch_a.id)
    # Branch-b OPERATOR for cross-branch tests
    branch_b_operator = await _make_user(db, role="OPERATOR", branch_id=branch_b.id)

    await db.commit()

    return {
        "branch_a": branch_a,
        "branch_b": branch_b,
        "client_a": client_a,
        "client_b": client_b,
        "app_a": app_a,
        "app_b": app_b,
        "users_by_role": users_by_role,
        "branch_b_operator": branch_b_operator,
    }


@pytest_asyncio.fixture
async def client_under_test():
    """Yield an httpx AsyncClient pointed at the FastAPI app with the
    lifespan fired.

    The router includes live inside the lifespan (see ``app/main.py``), so
    httpx.ASGITransport by itself returns 404. We drive the lifespan
    manually via ``app.router.lifespan_context``.
    """
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# 1. require_roles() — unit-level dependency check
# ---------------------------------------------------------------------------


class TestRequireRolesHelper:
    async def test_require_roles_returns_user_when_role_allowed(
        self, db, branches_users_apps,
    ):
        from app.core.security import require_roles

        checker = require_roles("OPERATOR", "BRANCH_ADMIN")
        operator = branches_users_apps["users_by_role"]["OPERATOR"]
        result = await checker(current_user=operator)
        assert result.id == operator.id

    async def test_require_roles_403_when_role_forbidden(
        self, db, branches_users_apps,
    ):
        from fastapi import HTTPException

        from app.core.security import require_roles

        checker = require_roles("REVIEWER_AUDITOR")
        operator = branches_users_apps["users_by_role"]["OPERATOR"]
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=operator)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# 2. assert_branch_scope() — unit-level
# ---------------------------------------------------------------------------


class TestAssertBranchScopeHelper:
    async def test_super_admin_bypass(self, db, branches_users_apps):
        from app.core.security import assert_branch_scope

        super_admin = branches_users_apps["users_by_role"]["SUPER_ADMIN"]
        app_b = branches_users_apps["app_b"]
        # Should not raise even though branch_ids differ.
        await assert_branch_scope(super_admin, app_b)

    async def test_same_branch_allowed(self, db, branches_users_apps):
        from app.core.security import assert_branch_scope

        operator_a = branches_users_apps["users_by_role"]["OPERATOR"]
        app_a = branches_users_apps["app_a"]
        await assert_branch_scope(operator_a, app_a)  # no raise

    async def test_cross_branch_denied(self, db, branches_users_apps):
        from fastapi import HTTPException

        from app.core.security import assert_branch_scope

        branch_b_operator = branches_users_apps["branch_b_operator"]
        app_a = branches_users_apps["app_a"]  # belongs to branch_a
        with pytest.raises(HTTPException) as exc:
            await assert_branch_scope(branch_b_operator, app_a)
        assert exc.value.status_code == 403

    async def test_branchless_user_denied(self, db, branches_users_apps):
        from fastapi import HTTPException

        from app.core.security import assert_branch_scope

        branchless = await _make_user(db, role="OPERATOR", branch_id=None)
        await db.commit()
        app_a = branches_users_apps["app_a"]
        with pytest.raises(HTTPException) as exc:
            await assert_branch_scope(branchless, app_a)
        assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# 3. /applications/{id} GET — branch scope via the route
# ---------------------------------------------------------------------------


class TestGetApplicationEndpoint:
    async def test_same_branch_get_succeeds(
        self, client_under_test, branches_users_apps,
    ):
        operator_a = branches_users_apps["users_by_role"]["OPERATOR"]
        app_a = branches_users_apps["app_a"]
        r = await client_under_test.get(
            f"/api/v1/applications/{app_a.id}",
            headers=_bearer(operator_a),
        )
        # Allowed; must NOT be 403.
        assert r.status_code == 200, r.text

    async def test_cross_branch_get_403(
        self, client_under_test, branches_users_apps,
    ):
        branch_b_operator = branches_users_apps["branch_b_operator"]
        app_a = branches_users_apps["app_a"]  # belongs to branch_a
        r = await client_under_test.get(
            f"/api/v1/applications/{app_a.id}",
            headers=_bearer(branch_b_operator),
        )
        assert r.status_code == 403, r.text
        assert "branch" in r.text.lower()

    async def test_super_admin_cross_branch_allowed(
        self, client_under_test, branches_users_apps,
    ):
        super_admin = branches_users_apps["users_by_role"]["SUPER_ADMIN"]
        app_a = branches_users_apps["app_a"]
        r = await client_under_test.get(
            f"/api/v1/applications/{app_a.id}",
            headers=_bearer(super_admin),
        )
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 4. POST /applications — role gate + create-in-own-branch
# ---------------------------------------------------------------------------


class TestCreateApplicationEndpoint:
    async def test_operator_can_create_in_own_branch(
        self, client_under_test, branches_users_apps,
    ):
        operator = branches_users_apps["users_by_role"]["OPERATOR"]
        branch_a = branches_users_apps["branch_a"]
        # Unique PAN per test run to avoid PAN-uniqueness collisions with
        # applications created in earlier test sessions. PAN column is
        # VARCHAR(10); format AAAAA9999A.
        unique_pan = (
            f"AB{uuid.uuid4().hex[:3].upper()}"
            f"{uuid.uuid4().int % 10000:04d}"
            f"{chr(ord('A') + (uuid.uuid4().int % 26))}"
        )
        payload = {
            "branch_id": str(branch_a.id),
            "business_name": "Test Co RBAC",
            "applicant_name": "Test",
            "mobile_number": "9876543210",
            "email": "test@example.com",
            "pan_number": unique_pan,
            "aadhaar_number": "123456789012",
            "workflow_type": "NEW_UDYAM",
        }
        r = await client_under_test.post(
            "/api/v1/applications",
            json=payload,
            headers=_bearer(operator),
        )
        # 201 on success; never 401/403 for an allowed role.
        assert r.status_code == 201, r.text

    async def test_reviewer_auditor_cannot_create(
        self, client_under_test, branches_users_apps,
    ):
        reviewer = branches_users_apps["users_by_role"]["REVIEWER_AUDITOR"]
        branch_a = branches_users_apps["branch_a"]
        payload = {
            "branch_id": str(branch_a.id),
            "business_name": "Should Not Exist",
            "applicant_name": "Test",
            "mobile_number": "9876543210",
            "email": "test@example.com",
            "pan_number": "ABCDE1234F",
            "aadhaar_number": "123456789012",
            "workflow_type": "NEW_UDYAM",
        }
        r = await client_under_test.post(
            "/api/v1/applications",
            json=payload,
            headers=_bearer(reviewer),
        )
        assert r.status_code == 403, r.text

    async def test_operator_cannot_create_in_other_branch(
        self, client_under_test, branches_users_apps,
    ):
        operator_a = branches_users_apps["users_by_role"]["OPERATOR"]
        branch_b = branches_users_apps["branch_b"]
        payload = {
            "branch_id": str(branch_b.id),
            "business_name": "Cross-branch attempt",
            "applicant_name": "Test",
            "mobile_number": "9876543210",
            "email": "test@example.com",
            "pan_number": "ABCDE1234F",
            "aadhaar_number": "123456789012",
            "workflow_type": "NEW_UDYAM",
        }
        r = await client_under_test.post(
            "/api/v1/applications",
            json=payload,
            headers=_bearer(operator_a),
        )
        assert r.status_code == 403, r.text
        assert "cross-branch" in r.text.lower()


# ---------------------------------------------------------------------------
# 5. POST /applications/{id}/nic/approve — OPERATOR explicitly forbidden
# ---------------------------------------------------------------------------


class TestNicApproveEndpoint:
    async def test_operator_gets_403(
        self, client_under_test, db, branches_users_apps,
    ):
        operator = branches_users_apps["users_by_role"]["OPERATOR"]
        # Force app into NIC_REVIEW regardless of fixture seed.
        app_a = branches_users_apps["app_a"]
        app_a.status = ApplicationState.NIC_REVIEW.value
        await db.commit()

        r = await client_under_test.post(
            f"/api/v1/applications/{app_a.id}/nic/approve",
            json={"selected_codes": ["12345"], "justification": "test"},
            headers=_bearer(operator),
        )
        assert r.status_code == 403, r.text

    async def test_reviewer_auditor_400_on_wrong_state(
        self, client_under_test, db, branches_users_apps,
    ):
        reviewer = branches_users_apps["users_by_role"]["REVIEWER_AUDITOR"]
        app_a = branches_users_apps["app_a"]  # status NEW
        await db.commit()

        r = await client_under_test.post(
            f"/api/v1/applications/{app_a.id}/nic/approve",
            json={"selected_codes": ["12345"], "justification": "test"},
            headers=_bearer(reviewer),
        )
        # Reviewer role passes the gate; failing state -> 400 from the endpoint.
        assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 6. PATCH /applications/{id}/validation-review — OPERATOR forbidden
# ---------------------------------------------------------------------------


class TestValidationReviewEndpoint:
    async def test_reviewer_can_review(
        self, client_under_test, db, branches_users_apps,
    ):
        reviewer = branches_users_apps["users_by_role"]["REVIEWER_AUDITOR"]
        app_a = branches_users_apps["app_a"]
        app_a.status = ApplicationState.VALIDATION_REVIEW.value
        await db.commit()

        r = await client_under_test.patch(
            f"/api/v1/applications/{app_a.id}/validation-review",
            json={"approve": True, "comments": "looks good"},
            headers=_bearer(reviewer),
        )
        # 200 on success, not 403.
        assert r.status_code == 200, r.text

    async def test_operator_cannot_review(
        self, client_under_test, db, branches_users_apps,
    ):
        operator = branches_users_apps["users_by_role"]["OPERATOR"]
        app_a = branches_users_apps["app_a"]
        app_a.status = ApplicationState.VALIDATION_REVIEW.value
        await db.commit()

        r = await client_under_test.patch(
            f"/api/v1/applications/{app_a.id}/validation-review",
            json={"approve": False},
            headers=_bearer(operator),
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 7. List /applications — branch filter
# ---------------------------------------------------------------------------


class TestListApplicationsEndpoint:
    async def test_super_admin_sees_all(
        self, client_under_test, branches_users_apps,
    ):
        super_admin = branches_users_apps["users_by_role"]["SUPER_ADMIN"]
        r = await client_under_test.get(
            "/api/v1/applications?limit=100",
            headers=_bearer(super_admin),
        )
        assert r.status_code == 200, r.text

    async def test_branch_admin_cannot_filter_other_branch(
        self, client_under_test, branches_users_apps,
    ):
        branch_admin = branches_users_apps["users_by_role"]["BRANCH_ADMIN"]
        branch_b = branches_users_apps["branch_b"]
        r = await client_under_test.get(
            f"/api/v1/applications?branch_id={branch_b.id}",
            headers=_bearer(branch_admin),
        )
        assert r.status_code == 403, r.text

    async def test_branch_admin_unfiltered_lists_own_branch(
        self, client_under_test, branches_users_apps,
    ):
        branch_admin = branches_users_apps["users_by_role"]["BRANCH_ADMIN"]
        r = await client_under_test.get(
            "/api/v1/applications?limit=100",
            headers=_bearer(branch_admin),
        )
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# 8. Unauthenticated — 401 (sanity check that require_roles still chains auth)
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    async def test_no_token_returns_401(self, client_under_test):
        r = await client_under_test.get("/api/v1/applications")
        assert r.status_code == 401, r.text

    async def test_garbage_token_returns_401(self, client_under_test):
        r = await client_under_test.get(
            "/api/v1/applications",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert r.status_code == 401, r.text
