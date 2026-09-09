"""Tests for Phase 12 — External Webhooks.

Coverage:
  * ``sign_payload`` — HMAC-SHA256 over the raw body, hex digest,
    constant-width output.
  * Tamper detection — flipping one byte of the body invalidates the
    signature.
  * ``deliver_once`` — happy-path 2xx writes one delivery row, sets
    ``last_status`` / ``last_triggered_at`` on the webhook, no error.
  * ``deliver_once`` — non-2xx still records an attempt; last_error
    is populated.
  * ``deliver_once`` — network exception is captured as ``error``,
    status_code stays NULL.
  * Retry loop — 3 attempts then 2xx on the 3rd, exactly 3 deliveries.
  * Retry exhausted — 4 attempts all failing, last_error set,
    ``delivered=0``, ``failed=1`` in the summary.
  * Pattern matcher — empty list subscribes to all, literal matches,
    glob matches, "*" wildcard.
  * Branch scoping — webhooks in a different branch are not fanned to.
  * Inactive webhook is skipped.
  * End-to-end — ``dispatch_event_webhooks`` writes the delivery row
    inside the same session.
  * API CRUD smoke — POST returns the secret once, GET never returns
    it, DELETE cascades the delivery rows.

Run: ``pytest backend/tests/test_webhooks.py -v``
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
import uuid
from typing import Any, Dict, List

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.domain import (  # noqa: E402
    Base,
    Branch,
    Client,
    User,
    Webhook,
    WebhookDelivery,
)
from app.services.webhook_delivery import (  # noqa: E402
    MAX_ATTEMPTS,
    RETRY_DELAYS_SECONDS,
    deliver_once,
    dispatch_event_webhooks,
    sign_payload,
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


async def _seed_branch(db: AsyncSession) -> Branch:
    branch = Branch(
        name=f"Webhook Branch {uuid.uuid4().hex[:6]}",
        code=f"WH{uuid.uuid4().hex[:6].upper()}",
        status="ACTIVE",
    )
    db.add(branch)
    await db.flush()
    return branch


async def _seed_user(db: AsyncSession, branch: Branch, role: str = "BRANCH_ADMIN") -> User:
    user = User(
        branch_id=branch.id,
        email=f"webhook-{uuid.uuid4().hex[:8]}@test.local",
        name=f"Webhook User {role}",
        role=role,
        password_hash="x",
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_webhook(
    db: AsyncSession,
    branch: Branch,
    *,
    url: str = "http://127.0.0.1:1/hook",
    is_active: bool = True,
    subscribed_events: List[str] | None = None,
) -> Webhook:
    hook = Webhook(
        branch_id=branch.id,
        name=f"hook-{uuid.uuid4().hex[:6]}",
        url=url,
        secret="test-secret-do-not-use-in-prod",
        subscribed_events=subscribed_events if subscribed_events is not None else [],
        is_active=is_active,
    )
    db.add(hook)
    await db.flush()
    return hook


def _make_transport(handler):
    """Build an httpx MockTransport from a sync handler ``(request) -> Response``."""

    def _go(request: httpx.Request) -> httpx.Response:
        return handler(request)

    return httpx.MockTransport(_go)


def _record_handler(requests: List[Dict[str, Any]], status_code: int = 200, body: bytes = b"OK"):
    """A transport handler that records every request and replies with status_code."""

    def _handle(request: httpx.Request) -> httpx.Response:
        try:
            text = request.content.decode("utf-8") if request.content else ""
        except Exception:
            text = ""
        requests.append(
            {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": text,
            }
        )
        return httpx.Response(status_code, content=body)

    return _handle


# ---------------------------------------------------------------------------
# sign_payload
# ---------------------------------------------------------------------------


class TestSigning:
    def test_signature_is_lowercase_hex_with_prefix(self):
        sig = sign_payload("secret", b"hello")
        assert sig.startswith("sha256=")
        hex_part = sig.split("=", 1)[1]
        assert len(hex_part) == 64
        assert hex_part == hex_part.lower()

    def test_signature_is_deterministic(self):
        assert sign_payload("k", b"x") == sign_payload("k", b"x")

    def test_signature_matches_stdlib_hmac(self):
        body = b"the body bytes"
        expected = hmac.new(b"key", body, hashlib.sha256).hexdigest()
        assert sign_payload("key", body) == f"sha256={expected}"

    def test_tampered_body_yields_different_signature(self):
        body = b"original"
        tampered = b"originaL"  # one byte flipped
        assert sign_payload("k", body) != sign_payload("k", tampered)

    def test_different_secret_yields_different_signature(self):
        body = b"same"
        assert sign_payload("k1", body) != sign_payload("k2", body)


# ---------------------------------------------------------------------------
# deliver_once
# ---------------------------------------------------------------------------


class TestDeliverOnce:
    @pytest.mark.asyncio
    async def test_happy_path_writes_delivery_and_updates_webhook(self, db):
        branch = await _seed_branch(db)
        hook = await _seed_webhook(db, branch)
        await db.commit()
        await db.refresh(hook)

        requests: List[Dict[str, Any]] = []
        transport = _make_transport(_record_handler(requests, 200, b"ok"))

        event = {
            "event": "STATE_TRANSITIONED.NEW.NIC_REVIEW",
            "event_id": str(uuid.uuid4()),
            "branch_id": str(branch.id),
            "application_id": str(uuid.uuid4()),
            "from": "NEW",
            "to": "NIC_REVIEW",
            "payload": {"actor": "operator-1"},
        }
        delivery = await deliver_once(hook, event, 1, db, transport=transport)
        await db.commit()

        assert len(requests) == 1
        sent = requests[0]
        assert sent["method"] == "POST"
        assert sent["url"] == "http://127.0.0.1:1/hook"
        assert sent["headers"]["x-taxla-event"] == "STATE_TRANSITIONED.NEW.NIC_REVIEW"
        assert sent["headers"]["x-taxla-delivery"] == event["event_id"]
        assert "x-taxla-signature" in sent["headers"]
        assert "x-taxla-timestamp" in sent["headers"]
        # Verify the signature independently — receiver-side check.
        expected = sign_payload("test-secret-do-not-use-in-prod", sent["body"].encode("utf-8"))
        assert sent["headers"]["x-taxla-signature"] == expected

        # DB rows
        assert delivery.status_code == 200
        assert delivery.response_body == "ok"
        assert delivery.error is None
        assert delivery.attempt_number == 1
        assert delivery.event_name == "STATE_TRANSITIONED.NEW.NIC_REVIEW"

        await db.refresh(hook)
        assert hook.last_status == 200
        assert hook.last_error is None
        assert hook.last_triggered_at is not None

    @pytest.mark.asyncio
    async def test_non_2xx_still_records_attempt_and_populates_last_error(self, db):
        branch = await _seed_branch(db)
        hook = await _seed_webhook(db, branch)
        await db.commit()
        await db.refresh(hook)

        transport = _make_transport(_record_handler([], 503, b"boom"))
        delivery = await deliver_once(
            hook,
            {"event": "x", "event_id": str(uuid.uuid4()), "branch_id": str(branch.id)},
            1,
            db,
            transport=transport,
        )
        await db.commit()
        assert delivery.status_code == 503
        assert delivery.error is None  # network was fine, just non-2xx
        await db.refresh(hook)
        assert hook.last_status == 503
        assert hook.last_error == "status=503"

    @pytest.mark.asyncio
    async def test_network_error_captured_as_error_text(self, db):
        branch = await _seed_branch(db)
        hook = await _seed_webhook(db, branch)
        await db.commit()
        await db.refresh(hook)

        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("dns dead", request=request)

        transport = _make_transport(boom)
        delivery = await deliver_once(
            hook,
            {"event": "x", "event_id": str(uuid.uuid4()), "branch_id": str(branch.id)},
            1,
            db,
            transport=transport,
        )
        await db.commit()
        assert delivery.status_code is None
        assert delivery.error is not None and "ConnectError" in delivery.error


# ---------------------------------------------------------------------------
# dispatch_event_webhooks / retry loop
# ---------------------------------------------------------------------------


class TestDispatchLoop:
    @pytest.mark.asyncio
    async def test_no_webhooks_returns_zero(self, db):
        branch = await _seed_branch(db)
        await db.commit()
        result = await dispatch_event_webhooks(
            {"event": "x", "branch_id": str(branch.id)},
            db,
            transport=_make_transport(_record_handler([], 200, b"ok")),
        )
        assert result == {"matched": 0, "delivered": 0, "failed": 0}

    @pytest.mark.asyncio
    async def test_inactive_webhook_skipped(self, db):
        branch = await _seed_branch(db)
        await _seed_webhook(db, branch, is_active=False)
        await db.commit()
        result = await dispatch_event_webhooks(
            {"event": "x", "branch_id": str(branch.id)},
            db,
            transport=_make_transport(_record_handler([], 200, b"ok")),
        )
        assert result["matched"] == 0

    @pytest.mark.asyncio
    async def test_subscribed_events_filter(self, db):
        branch = await _seed_branch(db)
        await _seed_webhook(
            db,
            branch,
            subscribed_events=["DOCUMENT_UPLOADED"],
        )
        await db.commit()
        transport = _make_transport(_record_handler([], 200, b"ok"))
        # Wrong event should NOT match — transport irrelevant.
        result = await dispatch_event_webhooks(
            {"event": "STATE_TRANSITIONED.X.Y", "branch_id": str(branch.id)},
            db,
            transport=transport,
        )
        assert result["matched"] == 0
        # Right event should match.
        result = await dispatch_event_webhooks(
            {"event": "DOCUMENT_UPLOADED", "branch_id": str(branch.id)},
            db,
            transport=transport,
        )
        assert result["matched"] == 1

    @pytest.mark.asyncio
    async def test_branch_scoping_other_branch_ignored(self, db):
        a = await _seed_branch(db)
        b = await _seed_branch(db)
        await _seed_webhook(db, b)
        await db.commit()
        result = await dispatch_event_webhooks(
            {"event": "x", "branch_id": str(a.id)},
            db,
            transport=_make_transport(_record_handler([], 200, b"ok")),
        )
        assert result["matched"] == 0

    @pytest.mark.asyncio
    async def test_retry_then_success_writes_one_row_per_attempt(self, db):
        branch = await _seed_branch(db)
        hook = await _seed_webhook(db, branch)
        await db.commit()
        await db.refresh(hook)

        responses = iter([500, 502, 200])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(next(responses), content=b"")

        transport = _make_transport(handler)
        sleeps: List[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        result = await dispatch_event_webhooks(
            {"event": "x", "branch_id": str(branch.id)},
            db,
            transport=transport,
            sleep_fn=fake_sleep,
        )
        await db.commit()
        assert result == {"matched": 1, "delivered": 1, "failed": 0}
        # Two failed attempts means two sleeps before the success.
        assert sleeps == [RETRY_DELAYS_SECONDS[0], RETRY_DELAYS_SECONDS[1]]
        # Three deliveries persisted (2 failures + 1 success).
        rows = (await db.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == hook.id)
            .order_by(WebhookDelivery.attempt_number)
        )).scalars().all()
        assert [r.attempt_number for r in rows] == [1, 2, 3]
        assert [r.status_code for r in rows] == [500, 502, 200]

    @pytest.mark.asyncio
    async def test_all_attempts_fail_marks_failed(self, db):
        branch = await _seed_branch(db)
        hook = await _seed_webhook(db, branch)
        await db.commit()
        await db.refresh(hook)

        transport = _make_transport(_record_handler([], 500, b""))
        sleeps: List[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        result = await dispatch_event_webhooks(
            {"event": "x", "branch_id": str(branch.id)},
            db,
            transport=transport,
            sleep_fn=fake_sleep,
        )
        await db.commit()
        assert result == {"matched": 1, "delivered": 0, "failed": 1}
        # MAX_ATTEMPTS rows; 3 sleeps between them.
        rows = (await db.execute(
            select(WebhookDelivery).where(WebhookDelivery.webhook_id == hook.id)
        )).scalars().all()
        assert len(rows) == MAX_ATTEMPTS
        assert sleeps == RETRY_DELAYS_SECONDS[: MAX_ATTEMPTS - 1]

        await db.refresh(hook)
        assert hook.last_status == 500
        assert hook.last_error == "status=500"


# ---------------------------------------------------------------------------
# Pattern matcher
# ---------------------------------------------------------------------------


class TestMatcher:
    def test_empty_list_subscribes_to_all(self):
        from app.services.webhook_delivery import _matches_any
        assert _matches_any("anything", []) is True

    def test_literal_match(self):
        from app.services.webhook_delivery import _matches_any
        assert _matches_any("DOCUMENT_UPLOADED", ["DOCUMENT_UPLOADED"]) is True
        assert _matches_any("DOCUMENT_UPLOADED", ["OTHER"]) is False

    def test_glob_match(self):
        from app.services.webhook_delivery import _matches_any
        assert _matches_any(
            "STATE_TRANSITIONED.NEW.NIC_REVIEW",
            ["STATE_TRANSITIONED.*.*"],
        ) is True
        assert _matches_any(
            "STATE_TRANSITIONED.NEW.NIC_REVIEW",
            ["STATE_TRANSITIONED.*.COMPLETED"],
        ) is False

    def test_wildcard(self):
        from app.services.webhook_delivery import _matches_any
        assert _matches_any("ANYTHING", ["*"]) is True


# ---------------------------------------------------------------------------
# API smoke tests
# ---------------------------------------------------------------------------


def _auth_header(user: User) -> Dict[str, str]:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestWebhookAPI:
    @pytest.mark.asyncio
    async def test_create_returns_secret_once_then_get_hides_it(
        self, db, client: TestClient
    ):
        branch = await _seed_branch(db)
        admin = await _seed_user(db, branch, role="BRANCH_ADMIN")
        await db.commit()

        resp = client.post(
            "/api/v1/webhooks",
            headers=_auth_header(admin),
            json={
                "name": "smoke-hook",
                "url": "https://hook.example.test/inbox",
                "subscribed_events": ["DOCUMENT_UPLOADED", "DOCUMENT_UPLOADED"],
                "is_active": True,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        secret = body["secret"]
        assert len(secret) == 64  # 32-byte hex
        created_id = body["id"]
        # Dedupe test — same event listed twice should appear once.
        assert body["subscribed_events"] == ["DOCUMENT_UPLOADED"]
        # Secret must NOT appear on subsequent reads.
        get_resp = client.get(
            f"/api/v1/webhooks/{created_id}", headers=_auth_header(admin)
        )
        assert get_resp.status_code == 200
        assert "secret" not in get_resp.json()

        # Cleanup so other tests in the session don't see this hook.
        client.delete(
            f"/api/v1/webhooks/{created_id}", headers=_auth_header(admin)
        )

    @pytest.mark.asyncio
    async def test_list_filters_to_caller_branch(self, db, client: TestClient):
        a = await _seed_branch(db)
        b = await _seed_branch(db)
        a_admin = await _seed_user(db, a, role="BRANCH_ADMIN")
        b_admin = await _seed_user(db, b, role="BRANCH_ADMIN")
        await _seed_webhook(db, a, url="https://a.test")
        await _seed_webhook(db, b, url="https://b.test")
        await db.commit()

        resp = client.get("/api/v1/webhooks", headers=_auth_header(a_admin))
        assert resp.status_code == 200
        urls = {row["url"] for row in resp.json()}
        assert urls == {"https://a.test"}

        resp = client.get("/api/v1/webhooks", headers=_auth_header(b_admin))
        assert resp.status_code == 200
        urls = {row["url"] for row in resp.json()}
        assert urls == {"https://b.test"}

    @pytest.mark.asyncio
    async def test_delete_cascades_deliveries(self, db, client: TestClient):
        branch = await _seed_branch(db)
        admin = await _seed_user(db, branch, role="BRANCH_ADMIN")
        hook = await _seed_webhook(db, branch)
        await db.commit()

        # Insert a delivery directly so we can prove the cascade fires.
        db.add(
            WebhookDelivery(
                webhook_id=hook.id,
                event_name="manual",
                attempt_number=1,
                status_code=200,
            )
        )
        await db.commit()

        resp = client.delete(
            f"/api/v1/webhooks/{hook.id}", headers=_auth_header(admin)
        )
        assert resp.status_code == 204
        # No more rows for this webhook id.
        survivors = (await db.execute(
            select(WebhookDelivery).where(WebhookDelivery.webhook_id == hook.id)
        )).scalars().all()
        assert survivors == []

    @pytest.mark.asyncio
    async def test_operator_role_cannot_create(self, db, client: TestClient):
        branch = await _seed_branch(db)
        operator = await _seed_user(db, branch, role="OPERATOR")
        await db.commit()
        resp = client.post(
            "/api/v1/webhooks",
            headers=_auth_header(operator),
            json={"name": "nope", "url": "https://x.test"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_list(self, client: TestClient):
        resp = client.get("/api/v1/webhooks")
        assert resp.status_code == 401