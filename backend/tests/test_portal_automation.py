"""Tests for Phase 09 — Real Udyam Portal Automation.

Run: pytest backend/tests/test_portal_automation.py -v

Strategy:
  * Boot the MOCK portal (aiohttp) once per module on a free port.
  * Override ``settings.PORTAL_MODE`` and ``settings.PORTAL_BASE_URL``
    for the duration of each test so ``get_selectors()`` resolves to
    ``http://127.0.0.1:<port>/``.
  * Seed a Branch / User / Client / Application / ExtractedData /
    NICReview / Workflow per test.
  * Drive the worker step by step — most tests call ``_Automation``
    methods directly to isolate one failure mode per test.

The legacy ``test_playwright_automation.py`` (run-as-main) is left
untouched. It will go stale under Phase 09 and is flagged for deletion
in Phase 12 cleanup.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import AsyncIterator, Tuple

import pytest
import pytest_asyncio
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Force MOCK mode for the entire module before importing the worker.
os.environ.setdefault("PORTAL_MODE", "MOCK")

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, async_engine  # noqa: E402
from app.models.domain import (  # noqa: E402
    Application,
    Base,
    Branch,
    Certificate,
    Client,
    ExtractedData,
    NicReview,
    User,
    Workflow,
)
from app.models.state import ApplicationState  # noqa: E402
from app.services.portal_selectors import (  # noqa: E402
    LIVE_SELECTORS,
    MOCK_SELECTORS,
    PortalSelectors,
    get_selectors,
)
from tests._mock_portal_server import start_mock_portal  # noqa: E402
from worker.playwright_agent import _Automation  # noqa: E402


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Make sure all tables exist before any test seeds data."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture(scope="module")
async def mock_portal_url() -> AsyncIterator[str]:
    """Start the MOCK aiohttp portal once per module; tear it down at the end."""
    async with start_mock_portal(host="127.0.0.1") as base_url:
        # ``settings`` is a Pydantic model — replace the field for the
        # duration of the module. The dataclass ``get_selectors()``
        # returns is frozen, but we re-resolve per-call so the swap is
        # visible immediately.
        original_mode = settings.PORTAL_MODE
        original_base = settings.PORTAL_BASE_URL
        settings.PORTAL_MODE = "MOCK"
        settings.PORTAL_BASE_URL = base_url
        try:
            yield base_url
        finally:
            settings.PORTAL_MODE = original_mode
            settings.PORTAL_BASE_URL = original_base


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    """Per-test session that rolls back on teardown."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def seeded_app(db: AsyncSession, mock_portal_url: str) -> Tuple[Application, Client]:
    """Seed Branch + User + Client + Application + Workflow + ExtractedData + NICReview.

    Returns ``(app, client)`` so tests can introspect either side.
    The application starts at ``PORTAL_RUNNING`` because that is the
    state the worker expects to find (it does not itself transition
    INTO PORTAL_RUNNING — the trigger / workflow service does that).
    """
    branch = Branch(
        name=f"PortalTest-{uuid.uuid4().hex[:6]}",
        code=f"P{uuid.uuid4().hex[:8].upper()}",
        status="ACTIVE",
    )
    db.add(branch)
    await db.flush()

    user = User(
        branch_id=branch.id,
        email=f"sa-{uuid.uuid4().hex[:6]}@test.local",
        name="Portal SA",
        role="SUPER_ADMIN",
        password_hash="x",
    )
    db.add(user)
    await db.flush()

    client = Client(
        branch_id=branch.id,
        business_name="Portal Test Co",
        applicant_name="Portal Test Applicant",
        mobile_number="9999999999",
        pan_number=f"ABCDE{uuid.uuid4().hex[:4].upper()}",
        aadhaar_number_hash="0" * 64,
    )
    db.add(client)
    await db.flush()

    app = Application(
        client_id=client.id,
        branch_id=branch.id,
        application_number=f"PORTAL-{uuid.uuid4().hex[:8].upper()}",
        status=ApplicationState.PORTAL_RUNNING.value,
        enterprise_type="Proprietorship",
        male_employees=2,
        female_employees=1,
        other_employees=0,
        child_labour_declaration=True,
        net_investment=100000,
        total_turnover=500000,
        interested_in_gem=True,
        interested_in_treds=False,
        interested_in_ncs=False,
        interested_in_nsic_b2b=False,
        district_industries_centre="Mumbai DIC",
    )
    db.add(app)
    await db.flush()

    wf = Workflow(
        application_id=app.id,
        current_node=app.status,
        status="RUNNING",
        context_json={},
    )
    db.add(wf)
    await db.flush()

    # Extracted data: plaintext Aadhaar + PAN. The worker reads these.
    db.add(ExtractedData(
        application_id=app.id,
        field_name="aadhaar_number",
        field_value="123456789012",
        final_confidence=0.99,
    ))
    db.add(ExtractedData(
        application_id=app.id,
        field_name="pan_number",
        field_value=client.pan_number,
        final_confidence=0.99,
    ))
    await db.flush()

    # Latest NIC review: pick 10104.
    db.add(NicReview(
        application_id=app.id,
        reviewer_id=user.id,
        selected_codes=["10104"],
        justification="test seed",
        decision="APPROVE",
    ))
    await db.commit()
    return app, client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_automation(
    app: Application, db: AsyncSession, mock_portal_url: str
) -> _Automation:
    """Build an ``_Automation`` instance bound to a fresh Playwright page.

    Tests can call its step methods directly. The browser is closed in
    the test's finally block via ``await page.context.close()``.
    """
    from playwright.async_api import async_playwright

    # Lazy import so the module is only loaded when a test actually needs
    # Playwright. CI may run this test file with Playwright not installed
    # (the LIVE mode is never exercised in CI) — the import error surfaces
    # only when a test tries to drive the browser.
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(accept_downloads=True)
    page = await context.new_page()
    # Stash the playwright handle on the page so tests can close it.
    page._pw_test_handle = (p, browser, context)  # type: ignore[attr-defined]
    selectors = get_selectors()
    return _Automation(app=app, page=page, selectors=selectors, db=db)


async def _close_page(page) -> None:
    """Tear down the Playwright handles opened by ``_make_automation``."""
    p, browser, context = page._pw_test_handle  # type: ignore[attr-defined]
    await context.close()
    await browser.close()
    await p.stop()


async def _publish_otp(app_id: uuid.UUID, code: str = "123456") -> None:
    """Push an OTP onto ``otp_<id>`` so the worker's listener picks it up."""
    r = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
    )
    try:
        await r.publish(f"otp_{app_id}", code)
    finally:
        await r.aclose()


# ---------------------------------------------------------------------------
# TestSelectors — registry sanity
# ---------------------------------------------------------------------------


class TestSelectors:
    """Verify the registry shape without exercising the portal."""

    def test_mock_selectors_have_every_required_field(self):
        required = {
            "base_url", "aadhaar_input", "aadhaar_validate_btn",
            "aadhaar_otp_input", "aadhaar_otp_validate_btn",
            "pan_input", "pan_validate_btn",
            "organisation_name", "organisation_type", "official_address",
            "nic_code", "nic_pick_first", "male_employees",
            "female_employees", "other_employees",
            "child_labour_checkbox", "net_investment", "total_turnover",
            "gem_checkbox", "treds_checkbox", "ncs_checkbox",
            "nsic_checkbox", "dic_input",
            "submit_btn", "success_heading", "uan_extractor",
        }
        for attr in required:
            assert hasattr(MOCK_SELECTORS, attr), f"MOCK_SELECTORS missing {attr}"

    def test_live_selectors_smoke(self):
        """LIVE selectors exist but are NOT exercised in CI — just check shape."""
        assert isinstance(LIVE_SELECTORS, PortalSelectors)
        assert LIVE_SELECTORS.uan_extractor is not None

    def test_get_selectors_resolves_mock_url(self, mock_portal_url: str):
        sel = get_selectors()
        assert sel.base_url == mock_portal_url
        # The active template carries MOCK_SELECTORS' string identifiers.
        assert sel.aadhaar_input == MOCK_SELECTORS.aadhaar_input
        assert sel.uan_extractor is MOCK_SELECTORS.uan_extractor


# ---------------------------------------------------------------------------
# TestSetup
# ---------------------------------------------------------------------------


class TestSetup:
    async def test_navigates_to_mock_portal_and_sees_aadhaar_form(
        self, seeded_app, db, mock_portal_url
    ):
        app, _ = seeded_app
        auto = await _make_automation(app, db, mock_portal_url)
        try:
            await auto._setup()
            # The aadhaar input should be present.
            assert await auto.page.query_selector(auto.selectors.aadhaar_input)
        finally:
            await _close_page(auto.page)


# ---------------------------------------------------------------------------
# TestAadhaarStep
# ---------------------------------------------------------------------------


class TestAadhaarStep:
    async def test_fill_aadhaar_transitions_to_otp_required(
        self, seeded_app, db, mock_portal_url
    ):
        app, _ = seeded_app
        auto = await _make_automation(app, db, mock_portal_url)
        try:
            await auto._setup()
            # Pre-load the aadhaar plaintext manually (in production this
            # is done by _fill_form, but _fill_aadhaar needs it before).
            auto.aadhaar_plain = "123456789012"
            await auto._fill_aadhaar()
            await db.refresh(app)
            assert app.status == ApplicationState.OTP_REQUIRED.value
        finally:
            await _close_page(auto.page)


# ---------------------------------------------------------------------------
# TestOtpHandoff
# ---------------------------------------------------------------------------


class TestOtpHandoff:
    async def test_otp_via_redis_channel_advances_to_pan(
        self, seeded_app, db, mock_portal_url
    ):
        app, _ = seeded_app
        auto = await _make_automation(app, db, mock_portal_url)
        try:
            await auto._setup()
            auto.aadhaar_plain = "123456789012"
            await auto._fill_aadhaar()

            # Start the wait_for_otp listener, then publish concurrently.
            otp_task = asyncio.create_task(auto._wait_for_otp())
            await asyncio.sleep(0.5)  # let the worker subscribe
            await _publish_otp(app.id)
            await otp_task

            await db.refresh(app)
            # Worker walks OTP_REQUIRED -> OTP_VERIFIED -> PORTAL_RUNNING
            # -> HUMAN_REVIEW -> APPROVED so the form step can begin.
            assert app.status == ApplicationState.APPROVED.value
        finally:
            await _close_page(auto.page)

    async def test_otp_timeout_transitions_to_exception(
        self, seeded_app, db, mock_portal_url, monkeypatch
    ):
        """Patch asyncio.timeout to expire immediately so we don't wait 5 minutes."""
        app, _ = seeded_app
        auto = await _make_automation(app, db, mock_portal_url)
        try:
            await auto._setup()
            auto.aadhaar_plain = "123456789012"
            await auto._fill_aadhaar()

            # Replace asyncio.timeout with an instant expiry context manager.
            class _InstantTimeout:
                async def __aenter__(self):
                    raise asyncio.TimeoutError()

                async def __aexit__(self, *exc):
                    return False

            monkeypatch.setattr(asyncio, "timeout", lambda *_a, **_k: _InstantTimeout())

            with pytest.raises(Exception):
                await auto._wait_for_otp()

            await db.refresh(app)
            assert app.status == ApplicationState.EXCEPTION.value
        finally:
            await _close_page(auto.page)
            monkeypatch.undo()


# ---------------------------------------------------------------------------
# TestPanStep
# ---------------------------------------------------------------------------


class TestPanStep:
    async def test_pan_validation_advances_to_form(
        self, seeded_app, db, mock_portal_url
    ):
        app, client = seeded_app
        auto = await _make_automation(app, db, mock_portal_url)
        try:
            await auto._setup()
            auto.aadhaar_plain = "123456789012"
            auto.pan_plain = client.pan_number
            await auto._fill_aadhaar()

            otp_task = asyncio.create_task(auto._wait_for_otp())
            await asyncio.sleep(0.5)
            await _publish_otp(app.id)
            await otp_task

            # Worker should now be on the PAN step.
            await auto._validate_pan()
            # No duplicate banner: it should just return without raising.
        finally:
            await _close_page(auto.page)

    async def test_pan_already_registered_transitions_to_duplicate(
        self, seeded_app, db, mock_portal_url
    ):
        """Boot the mock portal with ?pan_duplicate=1 so the banner shows."""
        from dataclasses import replace

        async with start_mock_portal(host="127.0.0.1") as dup_url:
            settings.PORTAL_BASE_URL = dup_url
            try:
                app, client = seeded_app
                # Override the base URL on the selectors so the page
                # actually shows the duplicate banner.
                auto = await _make_automation(app, db, dup_url)
                try:
                    await auto._setup()
                    # Re-navigate with the query param that flips the
                    # duplicate-PAN banner on in the mock JS.
                    await auto.page.goto(dup_url + "?pan_duplicate=1")
                    auto.aadhaar_plain = "123456789012"
                    auto.pan_plain = client.pan_number
                    await auto._fill_aadhaar()

                    otp_task = asyncio.create_task(auto._wait_for_otp())
                    await asyncio.sleep(0.5)
                    await _publish_otp(app.id)
                    await otp_task

                    with pytest.raises(Exception):
                        await auto._validate_pan()
                    await db.refresh(app)
                    assert app.status == ApplicationState.EXCEPTION.value
                finally:
                    await _close_page(auto.page)
            finally:
                settings.PORTAL_BASE_URL = mock_portal_url


# ---------------------------------------------------------------------------
# TestSubmit
# ---------------------------------------------------------------------------


class TestSubmit:
    async def test_submit_yields_uan_and_transitions_to_submitted(
        self, seeded_app, db, mock_portal_url
    ):
        app, client = seeded_app
        auto = await _make_automation(app, db, mock_portal_url)
        try:
            await auto._setup()
            auto.aadhaar_plain = "123456789012"
            auto.pan_plain = client.pan_number
            await auto._fill_aadhaar()
            otp_task = asyncio.create_task(auto._wait_for_otp())
            await asyncio.sleep(0.5)
            await _publish_otp(app.id)
            await otp_task
            await auto._validate_pan()
            await auto._fill_form()
            await auto._submit()
            assert auto.uan is not None
            assert auto.uan.startswith("UDYAM-")
            await db.refresh(app)
            assert app.status == ApplicationState.SUBMITTED.value
        finally:
            await _close_page(auto.page)


# ---------------------------------------------------------------------------
# TestCertificate
# ---------------------------------------------------------------------------


class TestCertificate:
    async def test_certificate_downloaded_and_row_inserted(
        self, seeded_app, db, mock_portal_url
    ):
        app, client = seeded_app
        auto = await _make_automation(app, db, mock_portal_url)
        try:
            await auto._setup()
            auto.aadhaar_plain = "123456789012"
            auto.pan_plain = client.pan_number
            await auto._fill_aadhaar()
            otp_task = asyncio.create_task(auto._wait_for_otp())
            await asyncio.sleep(0.5)
            await _publish_otp(app.id)
            await otp_task
            await auto._validate_pan()
            await auto._fill_form()
            await auto._submit()
            await auto._capture_certificate()
            # File exists on disk.
            assert auto.cert_path is not None
            assert os.path.exists(auto.cert_path)
            # Row inserted with UAN as registration_number.
            rows = (await db.execute(
                select(Certificate).where(Certificate.application_id == app.id)
            )).scalars().all()
            assert len(rows) == 1
            assert rows[0].registration_number == auto.uan
        finally:
            await _close_page(auto.page)


# ---------------------------------------------------------------------------
# TestFinalize
# ---------------------------------------------------------------------------


class TestFinalize:
    async def test_certificate_ready_to_completed(
        self, seeded_app, db, mock_portal_url
    ):
        app, _ = seeded_app
        # Pre-walk the application to CERTIFICATE_READY so _finalize can
        # transition CERTIFICATE_READY -> COMPLETED legally. The seeded
        # app already starts at PORTAL_RUNNING, so skip the first step.
        from app.core.state_machine import transition

        await transition(
            app, ApplicationState.HUMAN_REVIEW.value, None, db
        )
        await transition(
            app, ApplicationState.APPROVED.value, None, db
        )
        await transition(
            app, ApplicationState.SUBMITTING.value, None, db
        )
        await transition(
            app, ApplicationState.SUBMITTED.value, None, db
        )
        await transition(
            app, ApplicationState.CERTIFICATE_READY.value, None, db
        )
        await db.commit()

        auto = await _make_automation(app, db, mock_portal_url)
        try:
            await auto._finalize()
            await db.refresh(app)
            assert app.status == ApplicationState.COMPLETED.value
        finally:
            await _close_page(auto.page)


# ---------------------------------------------------------------------------
# TestErrorMatrix
# ---------------------------------------------------------------------------


class TestErrorMatrix:
    async def test_captcha_routes_to_human_review_required(
        self, seeded_app, db, mock_portal_url
    ):
        async with start_mock_portal(host="127.0.0.1") as cap_url:
            settings.PORTAL_BASE_URL = cap_url
            try:
                app, _ = seeded_app
                auto = await _make_automation(app, db, cap_url)
                try:
                    await auto._setup()
                    # Re-navigate with the query param that triggers the
                    # captcha iframe in the mock JS.
                    await auto.page.goto(cap_url + "?captcha=1")
                    auto.aadhaar_plain = "123456789012"
                    with pytest.raises(Exception):
                        await auto._fill_aadhaar()
                    await db.refresh(app)
                    assert app.status == ApplicationState.EXCEPTION.value
                finally:
                    await _close_page(auto.page)
            finally:
                settings.PORTAL_BASE_URL = mock_portal_url

    async def test_invalid_aadhaar_routes_to_human_review_required(
        self, seeded_app, db, mock_portal_url
    ):
        async with start_mock_portal(host="127.0.0.1") as bad_url:
            settings.PORTAL_BASE_URL = bad_url
            try:
                app, _ = seeded_app
                auto = await _make_automation(app, db, bad_url)
                try:
                    await auto._setup()
                    # Re-navigate with the query param that triggers the
                    # invalid-aadhaar banner in the mock JS.
                    await auto.page.goto(bad_url + "?invalid_aadhaar=1")
                    auto.aadhaar_plain = "123456789012"
                    with pytest.raises(Exception):
                        await auto._fill_aadhaar()
                    await db.refresh(app)
                    assert app.status == ApplicationState.EXCEPTION.value
                finally:
                    await _close_page(auto.page)
            finally:
                settings.PORTAL_BASE_URL = mock_portal_url