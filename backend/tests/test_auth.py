"""Phase 06 — Auth flow tests.

Verifies the cookie-based refresh + logout contract:

  * /login returns the access token in JSON AND sets an HttpOnly cookie.
  * /refresh reads the cookie, rotates, returns a new access token,
    and the old refresh token is rejected on a second call.
  * /logout revokes the cookie (subsequent /refresh fails).
  * /me rejects garbage Bearer tokens (still 401).
  * /me rejects refresh tokens used as access tokens (typ guard).

The Redis blacklist is exercised against the real Redis configured in
``app.core.config.settings``. If Redis is unreachable, the auth flow tests
should be skipped — they are not safe to run offline.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import (  # noqa: E402
    create_access_token,
    create_refresh_token,
)
from app.main import app  # noqa: E402 — the FastAPI instance under test
from app.models.domain import Base, Branch, User  # noqa: E402


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


async def _ensure_branch(db) -> Branch:
    branch = Branch(
        name="Auth Test Branch",
        code=f"AUTH{uuid.uuid4().hex[:6].upper()}",
        status="ACTIVE",
    )
    db.add(branch)
    await db.flush()
    return branch


async def _ensure_user(db, *, email: str, password: str, role: str, branch_id) -> User:
    from app.core.security import get_password_hash

    user = User(
        branch_id=branch_id,
        role=role,
        name="Auth Test User",
        email=email,
        password_hash=get_password_hash(password),
        status="ACTIVE",
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def active_user(db):
    """Provision a real User with a real bcrypt password for login."""
    branch = await _ensure_branch(db)
    email = f"auth-{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPass@123"
    user = await _ensure_user(
        db, email=email, password=password, role="OPERATOR", branch_id=branch.id,
    )
    await db.commit()
    return {"user": user, "email": email, "password": password, "branch": branch}


@pytest_asyncio.fixture
async def client_under_test():
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# 1. POST /auth/login — sets HttpOnly cookie
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_login_returns_access_token_in_body(
        self, client_under_test, active_user,
    ):
        r = await client_under_test.post(
            "/api/v1/auth/login",
            json={"username": active_user["email"], "password": active_user["password"]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["email"] == active_user["email"]

    async def test_login_sets_refresh_cookie(
        self, client_under_test, active_user,
    ):
        r = await client_under_test.post(
            "/api/v1/auth/login",
            json={"username": active_user["email"], "password": active_user["password"]},
        )
        assert r.status_code == 200
        cookie_header = r.headers.get("set-cookie", "")
        assert "taxla_refresh=" in cookie_header, cookie_header
        # HttpOnly marker — JavaScript cannot read the cookie.
        assert "HttpOnly" in cookie_header or "httponly" in cookie_header.lower()
        # Path-restricted to root so every request carries it.
        assert "Path=/" in cookie_header

    async def test_login_rejects_wrong_password(
        self, client_under_test, active_user,
    ):
        r = await client_under_test.post(
            "/api/v1/auth/login",
            json={"username": active_user["email"], "password": "wrong-password"},
        )
        assert r.status_code == 401, r.text

    async def test_login_rejects_unknown_email(
        self, client_under_test,
    ):
        r = await client_under_test.post(
            "/api/v1/auth/login",
            json={"username": "ghost@example.com", "password": "whatever"},
        )
        assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 2. POST /auth/refresh — rotation + blacklist
# ---------------------------------------------------------------------------


class TestRefresh:
    async def _login(self, client, active_user):
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": active_user["email"], "password": active_user["password"]},
        )
        assert r.status_code == 200
        return r

    async def test_refresh_returns_new_access_token(
        self, client_under_test, active_user,
    ):
        # ASGITransport's cookie jar doesn't auto-thread Set-Cookie back
        # into request cookies, so we hand-extract the cookie value.
        r = await self._login(client_under_test, active_user)
        cookie = r.headers["set-cookie"].split(";")[0]  # "taxla_refresh=<jwt>"

        r2 = await client_under_test.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": cookie},
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["access_token"]
        assert body["token_type"] == "bearer"
        # And the response itself sets a fresh refresh cookie.
        assert "taxla_refresh=" in r2.headers.get("set-cookie", "")

    async def test_refresh_rejects_old_token_after_rotation(
        self, client_under_test, active_user,
    ):
        r = await self._login(client_under_test, active_user)
        old_cookie = r.headers["set-cookie"].split(";")[0]

        r2 = await client_under_test.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": old_cookie},
        )
        assert r2.status_code == 200

        # Second refresh with the original cookie must fail — it was
        # added to the Redis blacklist when the first /refresh rotated.
        r3 = await client_under_test.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": old_cookie},
        )
        assert r3.status_code == 401, r3.text

    async def test_refresh_rejects_missing_cookie(
        self, client_under_test,
    ):
        r = await client_under_test.post("/api/v1/auth/refresh")
        assert r.status_code == 401, r.text

    async def test_refresh_rejects_garbage_cookie(
        self, client_under_test,
    ):
        r = await client_under_test.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": "taxla_refresh=not-a-real-jwt"},
        )
        assert r.status_code == 401, r.text

    async def test_refresh_rejects_access_token_as_refresh(
        self, client_under_test, active_user,
    ):
        # An access token (typ=access) used against /refresh must fail
        # so a stolen access token can't be promoted to a refresh session.
        access = create_access_token(subject=str(active_user["user"].id))
        r = await client_under_test.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": f"taxla_refresh={access}"},
        )
        assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 3. POST /auth/logout — revokes + clears cookie
# ---------------------------------------------------------------------------


class TestLogout:
    async def test_logout_clears_cookie_and_revokes(
        self, client_under_test, active_user,
    ):
        r = await client_under_test.post(
            "/api/v1/auth/login",
            json={"username": active_user["email"], "password": active_user["password"]},
        )
        cookie = r.headers["set-cookie"].split(";")[0]

        r2 = await client_under_test.post(
            "/api/v1/auth/logout",
            headers={"Cookie": cookie},
        )
        assert r2.status_code == 204

        # Server returns an immediate cookie clear.
        clear = r2.headers.get("set-cookie", "")
        assert "taxla_refresh=" in clear
        assert "Max-Age=0" in clear or "max-age=0" in clear.lower()

        # The refresh token is now in the Redis blacklist, so a /refresh
        # with the old cookie fails.
        r3 = await client_under_test.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": cookie},
        )
        assert r3.status_code == 401, r3.text

    async def test_logout_succeeds_without_cookie(
        self, client_under_test,
    ):
        # Logout must not depend on a valid session — logout from a
        # private window must work and not leak whether a session existed.
        r = await client_under_test.post("/api/v1/auth/logout")
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# 4. GET /auth/me — typ guard + Bearer auth
# ---------------------------------------------------------------------------


class TestMe:
    async def test_me_accepts_valid_access_token(
        self, client_under_test, active_user,
    ):
        token = create_access_token(subject=str(active_user["user"].id))
        r = await client_under_test.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["email"] == active_user["email"]

    async def test_me_rejects_refresh_token_as_bearer(
        self, client_under_test, active_user,
    ):
        # A refresh token sent as Authorization must be rejected. This
        # protects against an XSS stealing the access token and then
        # somehow gaining a refresh — the typ guard stops that.
        token = create_refresh_token(subject=str(active_user["user"].id))
        r = await client_under_test.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401, r.text

    async def test_me_rejects_garbage_token(
        self, client_under_test,
    ):
        r = await client_under_test.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert r.status_code == 401

    async def test_me_rejects_missing_token(
        self, client_under_test,
    ):
        r = await client_under_test.get("/api/v1/auth/me")
        assert r.status_code == 401