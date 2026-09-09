"""Phase 09 — Centralized portal selector registry.

Two flavours of selectors are defined here:

  * ``LIVE_SELECTORS`` — best-guess selectors for the real
    udyamregistration.gov.in portal. Documented but never exercised in CI.
    Maintainers should hand-update these if/when the portal changes.

  * ``MOCK_SELECTORS`` — selectors matching the recorded HTML fixture at
    ``tests/fixtures/mock_portal/index.html``. The test suite uses this
    exclusively. New selectors go here first; once MOCK passes, LIVE can
    be updated by hand.

``get_selectors()`` resolves the right one based on ``settings.PORTAL_MODE``.
The ``base_url`` of the resolved ``PortalSelectors`` instance is also
filled in at resolve-time so the worker has a single source of truth for
where to navigate.

We deliberately do NOT pull Playwright at import time — the registry is
plain data + a couple of callables. ``Page`` is only referenced inside
the typed callable signatures so importing this module does not require
Playwright to be installed (test collection works without it).
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Awaitable, Callable

from app.core.config import settings

if TYPE_CHECKING:  # pragma: no cover
    from playwright.async_api import Page

logger = logging.getLogger("taxla.portal_selectors")


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PortalSelectors:
    """Selectors + behaviour bindings for one portal instance.

    Field semantics are documented inline. Each selector is a CSS or
    Playwright-style locator string. ``uan_extractor`` is the only
    callable because it is the one place where the LIVE portal and the
    MOCK fixture differ in how the UAN is rendered.
    """

    base_url: str

    # Step 1 — Aadhaar
    aadhaar_input: str
    aadhaar_validate_btn: str
    aadhaar_invalid_banner: str  # portal shows this when the Aadhaar is rejected
    aadhaar_captcha_frame: str   # iframe indicating CAPTCHA appeared

    # Step 2 — OTP
    aadhaar_otp_input: str
    aadhaar_otp_validate_btn: str

    # Step 3 — PAN
    pan_input: str
    pan_validate_btn: str
    pan_already_registered_banner: str

    # Step 4 — Main form
    organisation_name: str
    organisation_type: str            # <select>
    official_address: str
    nic_code: str                     # input that triggers NIC autocomplete
    nic_pick_first: str               # click first result in portal's dropdown
    male_employees: str
    female_employees: str
    other_employees: str
    child_labour_checkbox: str
    net_investment: str
    total_turnover: str
    gem_checkbox: str
    treds_checkbox: str
    ncs_checkbox: str
    nsic_checkbox: str
    dic_input: str

    # Step 5 — Submit + success
    submit_btn: str
    success_heading: str              # locator for the success-page heading
    uan_extractor: Callable[["Page"], Awaitable[str]] = field(
        repr=False, compare=False
    )


# ---------------------------------------------------------------------------
# Mock portal extractor
# ---------------------------------------------------------------------------


async def _mock_uan_extractor(page: "Page") -> str:
    """Read the UAN from the MOCK portal's success page.

    The fixture renders it inside an ``<h2 id="uan-value">UDYAM-XX-00-1234567</h2>``.
    We assert the prefix because anything else is a fixture bug.
    """
    raw = (await page.text_content("#uan-value")) or ""
    raw = raw.strip()
    if not raw.startswith("UDYAM-"):
        raise ValueError(f"mock_uan_extractor: unexpected UAN text: {raw!r}")
    return raw


# ---------------------------------------------------------------------------
# LIVE portal extractor (best-effort)
# ---------------------------------------------------------------------------


async def _live_uan_extractor(page: "Page") -> str:
    """Best-effort extractor for the live portal.

    Real Udyam Registration Numbers follow ``UDYAM-XX-00-0000000`` where
    XX is the state code. We regex for that pattern in the page text.
    This is intentionally permissive — if the format ever changes, we
    fail loudly here rather than silently completing with a bogus UAN.
    """
    body_text = (await page.text_content("body")) or ""
    match = re.search(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", body_text)
    if not match:
        raise ValueError(
            "live_uan_extractor: no UAN matching UDYAM-XX-00-0000000 found "
            "in the live portal response body"
        )
    return match.group(0)


# ---------------------------------------------------------------------------
# Selector sets
# ---------------------------------------------------------------------------
# LIVE selectors are best-effort. They are NOT exercised in CI. If you
# change them, run the worker once by hand against the real portal with
# ``PORTAL_MODE=LIVE`` and confirm every step still works.


LIVE_SELECTORS = PortalSelectors(
    base_url="",  # filled in by get_selectors()
    # Aadhaar step on the real portal uses an input named "aadhaarNumber"
    # in a multi-step wizard. Field IDs shift during portal updates;
    # maintainers must verify against the live site.
    aadhaar_input='input[name="aadhaarNumber"]',
    aadhaar_validate_btn='button:has-text("Validate & Generate OTP")',
    aadhaar_invalid_banner='.alert-danger:has-text("Invalid Aadhaar")',
    aadhaar_captcha_frame='iframe[src*="recaptcha"], iframe[src*="hcaptcha"]',
    aadhaar_otp_input='input[name="otp"]',
    aadhaar_otp_validate_btn='button:has-text("Validate")',
    pan_input='input[name="pan"]',
    pan_validate_btn='button:has-text("Validate PAN")',
    pan_already_registered_banner='.alert-danger:has-text("PAN already registered")',
    organisation_name='input[name="orgName"]',
    organisation_type='select[name="orgType"]',
    official_address='textarea[name="address"]',
    nic_code='input[name="nicCode"]',
    nic_pick_first='.nic-suggestions li:first-child',
    male_employees='input[name="maleEmployees"]',
    female_employees='input[name="femaleEmployees"]',
    other_employees='input[name="otherEmployees"]',
    child_labour_checkbox='input[name="noChildLabour"]',
    net_investment='input[name="netInvestment"]',
    total_turnover='input[name="totalTurnover"]',
    gem_checkbox='input[name="optGem"]',
    treds_checkbox='input[name="optTreds"]',
    ncs_checkbox='input[name="optNcs"]',
    nsic_checkbox='input[name="optNsic"]',
    dic_input='input[name="dicName"]',
    submit_btn='button:has-text("Submit")',
    success_heading='h1:has-text("Registration Successful")',
    uan_extractor=_live_uan_extractor,
)


MOCK_SELECTORS = PortalSelectors(
    base_url="",  # filled in by get_selectors()
    aadhaar_input="#aadhaar_number",
    aadhaar_validate_btn="#btn_validate_generate_otp",
    aadhaar_invalid_banner="#aadhaar_invalid",
    aadhaar_captcha_frame="#captcha_frame",
    aadhaar_otp_input="#aadhaar_otp",
    aadhaar_otp_validate_btn="#btn_verify_otp",
    pan_input="#pan_number",
    pan_validate_btn="#btn_validate_pan",
    pan_already_registered_banner="#pan_already_registered",
    organisation_name="#organisation_name",
    organisation_type="#organisation_type",
    official_address="#official_address",
    nic_code="#nic_code",
    nic_pick_first="#nic_suggestion_first",
    male_employees="#male_employees",
    female_employees="#female_employees",
    other_employees="#other_employees",
    child_labour_checkbox="#no_child_labour",
    net_investment="#net_investment",
    total_turnover="#total_turnover",
    gem_checkbox="#opt_gem",
    treds_checkbox="#opt_treds",
    ncs_checkbox="#opt_ncs",
    nsic_checkbox="#opt_nsic",
    dic_input="#dic_name",
    submit_btn="#btn_submit",
    success_heading="#success_heading",
    uan_extractor=_mock_uan_extractor,
)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


def _resolve_base_url() -> str:
    """Resolve the base URL based on ``settings.PORTAL_MODE`` and ``settings.UDYAM_TARGET_URL``.

    1. Explicit test override: ``settings.PORTAL_BASE_URL``
    2. Configurable automation target: ``UDYAM_TARGET_URL``
    3. LIVE mode: ``settings.UDYAM_PORTAL_URL``
    4. Local mock fixture fallback
    """
    if settings.PORTAL_BASE_URL:
        return settings.PORTAL_BASE_URL

    target_url = os.environ.get("UDYAM_TARGET_URL") or getattr(settings, "UDYAM_TARGET_URL", "")
    if target_url:
        return target_url

    mode = (settings.PORTAL_MODE or "MOCK").upper()
    if mode == "LIVE":
        return settings.UDYAM_PORTAL_URL

    fixture_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures", "mock_portal", "index.html"))
    if os.path.exists(fixture_path):
        return f"file:///{fixture_path.replace(os.sep, '/')}"
    return "http://localhost:8000/mock-portal"


def get_selectors() -> PortalSelectors:
    """Return the active ``PortalSelectors`` instance.

    The dataclass is frozen, so we ``replace()`` it with the resolved
    ``base_url``. The callable (``uan_extractor``) carries over because
    it has ``compare=False, repr=False`` in the field spec.
    """
    mode = (settings.PORTAL_MODE or "MOCK").upper()
    template = LIVE_SELECTORS if mode == "LIVE" else MOCK_SELECTORS
    resolved = replace(template, base_url=_resolve_base_url())
    logger.debug("portal_selectors: mode=%s base_url=%s", mode, resolved.base_url)
    return resolved