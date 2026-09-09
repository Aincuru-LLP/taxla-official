"""Tests for Phase 13 — AI Agents live metrics endpoints.

Coverage:
  * GET /ai-agents/nic-matcher/metrics — counts, acceptance rate, tier
    distribution (keyword/vector/llm inferred from rationale text),
    top codes, recent activity.
  * GET /ai-agents/validator/metrics — counts, pass rate, decision
    distribution, failures by field, recent failures.
  * GET /ai-agents/portal-driver/metrics — run counts (24h/7d/total),
    queue depth, status distribution, success rate, recent runs.
  * GET /ai-agents/portal-driver/queue — applications currently parked
    in a portal-driver state.
  * Auth — unauthenticated callers get 401.

Run: ``pytest backend/tests/test_ai_agents_metrics.py -v``
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.domain import (  # noqa: E402
    Application,
    Base,
    Branch,
    Client,
    ExtractedData,
    NICSuggestion,
    PortalSession,
    User,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


async def _seed_branch(db: AsyncSession) -> Branch:
    branch = Branch(
        name=f"AIAgents Branch {uuid.uuid4().hex[:6]}",
        code=f"AI{uuid.uuid4().hex[:6].upper()}",
        status="ACTIVE",
    )
    db.add(branch)
    await db.flush()
    return branch


async def _seed_user(db: AsyncSession, branch: Branch) -> User:
    user = User(
        branch_id=branch.id,
        email=f"ai-{uuid.uuid4().hex[:8]}@test.local",
        name="AI Agents Tester",
        role="BRANCH_ADMIN",
        password_hash="x",
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_client(db: AsyncSession, branch: Branch) -> Client:
    client = Client(
        branch_id=branch.id,
        business_name=f"Client {uuid.uuid4().hex[:6]}",
        applicant_name=f"Applicant {uuid.uuid4().hex[:6]}",
        mobile_number=f"9999{uuid.uuid4().hex[:6].upper()}",
        pan_number=f"ABCDE{uuid.uuid4().hex[:3].upper()}",
        aadhaar_number_hash=uuid.uuid4().hex + uuid.uuid4().hex[:0],
        email=f"client-{uuid.uuid4().hex[:6]}@test.local",
    )
    db.add(client)
    await db.flush()
    return client


async def _seed_application(
    db: AsyncSession, branch: Branch, client: Client, status: str = "NEW"
) -> Application:
    app_row = Application(
        client_id=client.id,
        branch_id=branch.id,
        application_number=f"UDYAM-{uuid.uuid4().hex[:10].upper()}",
        status=status,
    )
    db.add(app_row)
    await db.flush()
    return app_row


def _auth_header(user: User) -> dict:
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# NIC matcher
# ---------------------------------------------------------------------------


class TestNicMatcherMetrics:
    @pytest.mark.asyncio
    async def test_returns_aggregated_payload(self, db, client: TestClient):
        branch = await _seed_branch(db)
        user = await _seed_user(db, branch)
        cli = await _seed_client(db, branch)
        await db.commit()
        # Three suggestions: 1 keyword, 1 vector, 1 llm. Two approved.
        for rationale, approved, conf in [
            ("keyword match on 'manufacturing'", True, 0.91),
            ("vector cosine sim 0.74", False, 0.62),
            ("llm rerank top-1", True, 0.83),
        ]:
            app_row = await _seed_application(db, branch, cli)
            db.add(
                NICSuggestion(
                    application_id=app_row.id,
                    nic_code_2digit="10",
                    nic_code_4digit="1010",
                    nic_code_5digit="10101",
                    description="manufacturing of xyz",
                    confidence=Decimal(str(conf)),
                    rationale=rationale,
                    approved=approved,
                )
            )
        await db.commit()

        resp = client.get(
            "/api/v1/ai-agents/nic-matcher/metrics", headers=_auth_header(user)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Top-level shape
        for key in (
            "window_24h_searches",
            "window_7d_searches",
            "acceptance_rate_7d",
            "tier_distribution",
            "top_codes",
            "recent",
        ):
            assert key in body, f"missing {key}"

        # Tier distribution has all three buckets summing to 1.0
        tier = body["tier_distribution"]
        assert set(tier.keys()) == {"keyword", "vector", "llm"}
        assert abs(sum(tier.values()) - 1.0) < 0.01

        # Acceptance rate = 2/3
        assert body["acceptance_rate_7d"] == pytest.approx(0.6667, rel=0.05)

        # Top codes: at least one entry, count >= 1
        assert body["top_codes"], "top_codes empty"
        assert body["top_codes"][0]["count"] >= 1

        # Recent: at most 8 entries, each with expected keys
        assert 1 <= len(body["recent"]) <= 8
        assert all("code" in r and "at" in r for r in body["recent"])

    @pytest.mark.asyncio
    async def test_fresh_branch_returns_zeros(self, db, client: TestClient):
        # Create a fresh branch with no apps; the metrics endpoints are
        # branch-agnostic (they aggregate globally), so we only assert the
        # shape and that no crash happens — a future branch-scoped refactor
        # should add real per-branch zeroing here.
        branch = await _seed_branch(db)
        user = await _seed_user(db, branch)
        await db.commit()

        resp = client.get(
            "/api/v1/ai-agents/nic-matcher/metrics", headers=_auth_header(user)
        )
        assert resp.status_code == 200
        body = resp.json()
        # Shape always present.
        for key in (
            "window_24h_searches",
            "window_7d_searches",
            "acceptance_rate_7d",
            "tier_distribution",
            "top_codes",
            "recent",
        ):
            assert key in body
        # Tier distribution sums to 1.0 (degenerate case → all zero).
        assert abs(sum(body["tier_distribution"].values()) - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: TestClient):
        resp = client.get("/api/v1/ai-agents/nic-matcher/metrics")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class TestValidatorMetrics:
    @pytest.mark.asyncio
    async def test_returns_pass_fail_review_breakdown(self, db, client: TestClient):
        branch = await _seed_branch(db)
        user = await _seed_user(db, branch)
        cli = await _seed_client(db, branch)
        # Commit so get_current_user can load the user by id.
        await db.commit()

        # Baseline before we add rows (the endpoint is global, so other
        # tests in the session may have left ExtractedData rows behind).
        pre_resp = client.get(
            "/api/v1/ai-agents/validator/metrics", headers=_auth_header(user)
        )
        assert pre_resp.status_code == 200, pre_resp.text
        pre = pre_resp.json()
        pass_before = pre["decisions"].get("PASS", 0)
        fail_before = pre["decisions"].get("FAIL", 0)
        review_before = pre["decisions"].get("REVIEW", 0)
        failures_before = pre["failures_by_field"].get("gstin", 0)
        total_before = pre["window_7d_validations"]
        avg_before = pre["avg_confidence_7d"] or 0.0

        # Two PASS, one FAIL, one REVIEW on different fields.
        app_row = await _seed_application(db, branch, cli)
        decisions = [
            ("pan", "ABCDE1234F", "PASS", 0.97),
            ("aadhaar", "123412341234", "PASS", 0.92),
            ("gstin", "BADGSTIN", "FAIL", 0.41),
            ("pin", "56000", "REVIEW", 0.55),
        ]
        for field, value, decision, conf in decisions:
            db.add(
                ExtractedData(
                    application_id=app_row.id,
                    field_name=field,
                    field_value=value,
                    review_decision=decision,
                    final_confidence=Decimal(str(conf)),
                )
            )
        await db.commit()

        resp = client.get(
            "/api/v1/ai-agents/validator/metrics", headers=_auth_header(user)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Each bucket grew by exactly the count we seeded (the endpoint
        # is global, so absolute numbers depend on prior tests — but the
        # *delta* is fully under this test's control).
        assert body["decisions"]["PASS"] == pass_before + 2
        assert body["decisions"]["FAIL"] == fail_before + 1
        assert body["decisions"]["REVIEW"] == review_before + 1
        assert body["failures_by_field"]["gstin"] == failures_before + 1
        assert body["window_7d_validations"] == total_before + 4
        # Average confidence moves but stays in [0, 1].
        assert body["avg_confidence_7d"] is not None
        assert 0.0 <= body["avg_confidence_7d"] <= 1.0
        assert isinstance(body["recent_failures"], list)

    @pytest.mark.asyncio
    async def test_fresh_branch_returns_shape(self, db, client: TestClient):
        branch = await _seed_branch(db)
        user = await _seed_user(db, branch)
        await db.commit()

        resp = client.get(
            "/api/v1/ai-agents/validator/metrics", headers=_auth_header(user)
        )
        assert resp.status_code == 200
        body = resp.json()
        for key in (
            "window_24h_validations",
            "window_7d_validations",
            "pass_rate_7d",
            "decisions",
            "failures_by_field",
            "avg_confidence_7d",
            "recent_failures",
        ):
            assert key in body
        assert isinstance(body["decisions"], dict)
        assert isinstance(body["recent_failures"], list)


# ---------------------------------------------------------------------------
# Portal driver
# ---------------------------------------------------------------------------


class TestPortalDriverMetrics:
    @pytest.mark.asyncio
    async def test_returns_throughput_and_queue_depth(
        self, db, client: TestClient
    ):
        branch = await _seed_branch(db)
        user = await _seed_user(db, branch)
        cli = await _seed_client(db, branch)
        # Commit so get_current_user can load the user by id.
        await db.commit()

        # Baseline (metrics are global — other tests may have seeded rows).
        pre_resp = client.get(
            "/api/v1/ai-agents/portal-driver/metrics", headers=_auth_header(user)
        )
        assert pre_resp.status_code == 200, pre_resp.text
        pre = pre_resp.json()
        queue_before = pre["queue_depth"]
        completed_before = pre["completed_7d"]
        submitted_before = pre["submitted_7d"]
        exception_before = pre["exception_7d"]

        # Two apps in SUBMITTED, one in EXCEPTION (drives success rate).
        submitted_a = await _seed_application(db, branch, cli, status="SUBMITTED")
        submitted_b = await _seed_application(db, branch, cli, status="SUBMITTED")
        exception = await _seed_application(db, branch, cli, status="EXCEPTION")
        # One app parked in OTP_REQUIRED — counts toward queue depth.
        parked = await _seed_application(db, branch, cli, status="OTP_REQUIRED")

        # A portal session per application
        for app_row in (submitted_a, submitted_b, exception, parked):
            db.add(
                PortalSession(
                    application_id=app_row.id,
                    session_status="COMPLETED"
                    if app_row.status in ("SUBMITTED", "EXCEPTION")
                    else "OTP_REQUIRED",
                    last_checkpoint="submit",
                )
            )
        await db.commit()

        resp = client.get(
            "/api/v1/ai-agents/portal-driver/metrics", headers=_auth_header(user)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Each bucket grew by exactly the rows we added.
        assert body["queue_depth"] == queue_before + 1
        assert body["completed_7d"] == completed_before + 3
        assert body["submitted_7d"] == submitted_before + 2
        assert body["exception_7d"] == exception_before + 1
        # Status distribution should include at least COMPLETED + OTP_REQUIRED
        assert "COMPLETED" in body["status_distribution"]
        assert body["total_runs"] >= 4
        # Success rate is bounded and non-negative.
        assert 0.0 <= body["success_rate_7d"] <= 1.0

    @pytest.mark.asyncio
    async def test_queue_lists_active_applications(
        self, db, client: TestClient
    ):
        branch = await _seed_branch(db)
        user = await _seed_user(db, branch)
        cli = await _seed_client(db, branch)
        await db.commit()

        parked = await _seed_application(db, branch, cli, status="OTP_REQUIRED")
        finished = await _seed_application(db, branch, cli, status="SUBMITTED")
        await db.commit()

        resp = client.get(
            "/api/v1/ai-agents/portal-driver/queue", headers=_auth_header(user)
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()}
        assert str(parked.id) in ids
        assert str(finished.id) not in ids


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    @pytest.mark.asyncio
    async def test_all_endpoints_require_auth(self, client: TestClient):
        for path in (
            "/api/v1/ai-agents/nic-matcher/metrics",
            "/api/v1/ai-agents/validator/metrics",
            "/api/v1/ai-agents/portal-driver/metrics",
            "/api/v1/ai-agents/portal-driver/queue",
        ):
            resp = client.get(path)
            assert resp.status_code == 401, f"{path} should require auth"
