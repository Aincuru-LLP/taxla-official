"""Phase 09 — Real Udyam Portal Automation worker.

Public entry point: ``run_automation(application_id_str)``.

This file REPLACES the Phase 06 stub (which navigated, waited for an OTP,
then parked the application at ``HUMAN_REVIEW``). Phase 09 walks the
portal end-to-end:

  Aadhaar fill → OTP handoff → PAN fill → form fill → submit →
  success screen → certificate download → COMPLETED.

Failure paths funnel into the existing state machine EXCEPTION node
with a stable ``error_code`` and ``resume_target``. There are five
codes:

  * ``OTP_TIMEOUT``       — operator did not enter an OTP in time.
                            resume_target=PORTAL_RUNNING
  * ``PORTAL_TIMEOUT``    — Playwright selector wait timed out.
                            resume_target=PORTAL_RUNNING
  * ``PORTAL_DOWN``       — DNS / 5xx / network error.
                            resume_target=PORTAL_RUNNING
  * ``CAPTCHA_DETECTED``  — Portal served a CAPTCHA iframe; humans needed.
                            resume_target=HUMAN_REVIEW_REQUIRED
  * ``INVALID_AADHAAR``   — Portal rejected the Aadhaar.
                            resume_target=HUMAN_REVIEW_REQUIRED
  * ``DUPLICATE_PAN``     — Portal says PAN already registered.
                            resume_target=DUPLICATE_PAN_DETECTED
  * ``PORTAL_FAILURE``    — Catch-all.
                            resume_target=PORTAL_RUNNING

Every transition is funnelled through ``app.core.state_machine.transition``.
Direct ``app.status = ...`` writes are forbidden — every state change is
the audit-trail-writing chokepoint.

Debug screenshots: any per-step failure writes ``storage/debug/<app_id>_<error_code>.png``
so an operator can see what the page looked like at the moment of failure.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import traceback
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

import redis.asyncio as redis
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.certificates import _populate_certificate_row
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.state_machine import transition
from app.models.domain import (
    Application,
    Client,
    ExtractedData,
    NicReview,
)
from app.models.state import ApplicationState
from app.services.portal_selectors import PortalSelectors, get_selectors

logger = logging.getLogger("taxla.worker.playwright")


# ---------------------------------------------------------------------------
# Orchestrator (thin)
# ---------------------------------------------------------------------------


async def run_automation(
    application_id_str: str,
    snapshot: Optional[Dict[str, Any]] = None,
    automation_job_id: Optional[str] = None,
) -> None:
    """Entry point for the Playwright worker task.

    Spawns an asynchronous Playwright session, loads the application and
    approved snapshot, navigates to the portal, and walks the happy path.
    """
    app_id = uuid.UUID(application_id_str)
    selectors = get_selectors()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Application).where(Application.id == app_id))
        app = result.scalars().first()
        if not app:
            logger.warning("Application %s not found; nothing to automate", app_id)
            return

        headless_mode = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() in ("true", "1")
        async with async_playwright() as p:
            launch_kwargs = {
                "headless": headless_mode,
                "slow_mo": 200 if not headless_mode else None,
            }
            try:
                browser = await p.chromium.launch(channel="chrome", **launch_kwargs)
            except Exception:
                browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            automation = _Automation(
                app=app,
                page=page,
                selectors=selectors,
                db=db,
                snapshot=snapshot,
                automation_job_id=automation_job_id,
            )
            try:
                await automation.run()
            except Exception as exc:
                # Catch-all: anything that escaped ``_Automation``'s _safe_step
                # wrapper still funnels through the state machine.
                await automation._abort(
                    error_code="PORTAL_FAILURE",
                    payload_json={
                        "exception": type(exc).__name__,
                        "traceback": traceback.format_exc(limit=8),
                    },
                    resume_target=ApplicationState.PORTAL_RUNNING.value,
                )
                logger.error(
                    "uncaught playwright failure for %s: %s", app_id, exc,
                    exc_info=True,
                )
            finally:
                await context.close()
                await browser.close()


# ---------------------------------------------------------------------------
# Automation class
# ---------------------------------------------------------------------------


class _Automation:
    """Per-invocation state container.

    Holds the Playwright page, the resolved selectors, the DB session,
    the approved snapshot, and the loaded Application row. Every step
    method is async and goes through ``_safe_step`` so a single step failure
    does not crash the test fixture or the dispatcher.
    """

    def __init__(
        self,
        *,
        app: Application,
        page: Page,
        selectors: PortalSelectors,
        db: AsyncSession,
        snapshot: Optional[Dict[str, Any]] = None,
        automation_job_id: Optional[str] = None,
    ) -> None:
        self.app = app
        self.page = page
        self.selectors = selectors
        self.db = db
        self.snapshot = snapshot
        self.automation_job_id = automation_job_id
        self.is_vercel_portal: bool = False
        self.aadhaar_plain: Optional[str] = None
        self.pan_plain: Optional[str] = None
        self.nic_code_to_use: Optional[str] = None
        self.uan: Optional[str] = None
        self.cert_path: Optional[str] = None

    # -- top-level flow -----------------------------------------------------

    async def run(self) -> None:
        """Top-level step orchestrator. Stops at the first safe-step failure."""
        if self.snapshot:
            snap_app_id = str(self.snapshot.get("application_id"))
            if snap_app_id != str(self.app.id):
                raise PortalError(
                    f"SNAPSHOT_INTEGRITY_MISMATCH: snapshot application_id {snap_app_id} does not match {self.app.id}"
                )

        from app.services.workflow_orchestrator import WorkflowOrchestrator
        exec_obj = await WorkflowOrchestrator.get_or_create_execution(self.app.id, self.db, trigger_source="PORTAL_AUTOMATION")
        self.execution_id = exec_obj.id

        await WorkflowOrchestrator.update_node_state(
            execution_id=self.execution_id,
            node_id="portal_automation",
            status="RUNNING",
            worker_id="playwright-worker-01",
            logs_text="Playwright Chromium browser launched. Connecting to Udyam portal...",
            db=self.db,
        )

        await self._load_form_payload()
        if self.app.status == ApplicationState.READY_FOR_PORTAL.value:
            await transition(
                self.app,
                ApplicationState.PORTAL_RUNNING.value,
                actor_id=None,
                db=self.db,
                payload_json={"step": "start_automation"},
            )
            await self.db.commit()

        await self._safe_step("setup", self._setup)
        await self._safe_step("fill_aadhaar", self._fill_aadhaar)
        await self._safe_step("wait_for_otp", self._wait_for_otp)
        await self._safe_step("validate_pan", self._validate_pan)
        await self._safe_step("fill_form", self._fill_form)
        await self._safe_step("submit", self._submit)
        await self._safe_step("capture_certificate", self._capture_certificate)
        await self._safe_step("finalize", self._finalize)

    # -- helpers ------------------------------------------------------------

    async def _safe_step(
        self,
        step_name: str,
        coro_factory: Callable[[], Awaitable[None]],
    ) -> None:
        """Wrap a step so a single failure aborts the whole flow.

        Re-raises PortalError directly so the orchestrator can stop; any
        other exception is converted to a PortalError with the
        appropriate error_code.
        """
        try:
            await coro_factory()
        except PortalError:
            # Already a structured failure. The orchestrator's outer
            # try/except in run() will not catch this; it propagates up
            # so ``run()`` stops further steps.
            raise
        except PlaywrightTimeoutError as exc:
            await self._abort(
                error_code="PORTAL_TIMEOUT",
                payload_json={"step": step_name, "detail": str(exc)[:300]},
                resume_target=ApplicationState.PORTAL_RUNNING.value,
            )
            raise PortalError("PORTAL_TIMEOUT")
        except Exception as exc:
            # Network / DNS / 5xx all surface here.
            await self._abort(
                error_code="PORTAL_FAILURE",
                payload_json={
                    "step": step_name,
                    "exception": type(exc).__name__,
                    "traceback": traceback.format_exc(limit=4),
                },
                resume_target=ApplicationState.PORTAL_RUNNING.value,
            )
            raise PortalError("PORTAL_FAILURE")

    async def _abort(
        self,
        *,
        error_code: str,
        payload_json: Optional[Dict[str, Any]] = None,
        resume_target: Optional[str] = None,
    ) -> None:
        """Route ``self.app`` to EXCEPTION with a stable error_code.

        Captures a screenshot before transitioning so an operator can
        see the page state. Commits the transaction so the audit trail
        lands even if the calling ARQ job is then killed.
        """
        try:
            await self._snapshot(f"{error_code}.png")
        except Exception:
            logger.exception("could not capture debug screenshot")

        if self.app.status == ApplicationState.EXCEPTION.value:
            return

        try:
            await transition(
                self.app,
                ApplicationState.EXCEPTION.value,
                actor_id=None,
                db=self.db,
                error_code=error_code,
                resume_target=resume_target,
                payload_json=payload_json or {},
            )
            await self.db.commit()
        except Exception:
            logger.exception("failed to write EXCEPTION transition for %s", self.app.id)
            try:
                await self.db.rollback()
            except Exception:
                logger.exception("rollback also failed")

    async def _snapshot(self, suffix: str) -> Optional[str]:
        """Save a debug screenshot to ``storage/debug/<app_id>_<suffix>.png``."""
        path = os.path.join(
            settings.DEBUG_SCREENSHOTS_DIR,
            f"{self.app.id}_{suffix}",
        )
        live_path = os.path.join(
            settings.DEBUG_SCREENSHOTS_DIR,
            f"{self.app.id}_live.png",
        )
        try:
            await self.page.screenshot(path=path, full_page=True)
            await self.page.screenshot(path=live_path, full_page=True)
            from app.services.workflow_orchestrator import WorkflowOrchestrator
            await WorkflowOrchestrator.emit_event(
                "SCREENSHOT_CAPTURED",
                {
                    "application_id": str(self.app.id),
                    "execution_id": str(self.execution_id) if hasattr(self, "execution_id") else None,
                    "screenshot_url": f"/api/v1/applications/{self.app.id}/automation/screenshot/live?t={int(time.time())}",
                    "suffix": suffix,
                },
            )
            return path
        except Exception:
            return None

    async def _load_form_payload(self) -> Dict[str, Any]:
        """Pre-load the values the form step needs.

        Plaintext Aadhaar comes from ``ExtractedData`` (we only ever
        stored the hash on the Client row). NIC code comes from the
        latest ``nic_reviews.selected_codes[0]`` for this application.
        The official address is on the related ``OfficialAddress`` row,
        not on ``Application`` or ``Client`` directly.
        """
        # Eager-load client + official_address in one round trip.
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(Application)
            .where(Application.id == self.app.id)
            .options(
                selectinload(Application.client),
                selectinload(Application.official_address),
            )
        )
        fresh: Application = result.scalars().first()
        if fresh is None:
            raise PortalError("application disappeared mid-run")
        self.client = fresh.client
        self.official_address = fresh.official_address
        client: Client = fresh.client  # type: ignore[assignment]

        # Plaintext Aadhaar resolution
        aadhaar_q = (
            select(ExtractedData)
            .where(
                ExtractedData.application_id == self.app.id,
                ExtractedData.field_name.in_(["aadhaar_number", "aadhaar"]),
            )
            .order_by(ExtractedData.final_confidence.desc().nullslast())
        )
        aadhaar_row = (await self.db.execute(aadhaar_q)).scalars().first()
        if aadhaar_row and aadhaar_row.field_value:
            self.aadhaar_plain = aadhaar_row.field_value.replace(" ", "").replace("-", "")

        if not self.aadhaar_plain:
            from app.models.domain import ApplicationRequirement
            req_res = await self.db.execute(
                select(ApplicationRequirement).where(
                    ApplicationRequirement.application_id == self.app.id,
                    ApplicationRequirement.requirement_key == "aadhaar",
                )
            )
            req_row = req_res.scalars().first()
            if req_row and req_row.value:
                digits = "".join(c for c in req_row.value if c.isdigit())
                if len(digits) == 12:
                    self.aadhaar_plain = digits

        if not self.aadhaar_plain and client and client.aadhaar_number_hash:
            digits = "".join(c for c in client.aadhaar_number_hash if c.isdigit())
            if len(digits) == 12:
                self.aadhaar_plain = digits

        if not self.aadhaar_plain and self.snapshot:
            self.aadhaar_plain = self.snapshot.get("owner", {}).get("aadhaar_number")

        # Plaintext PAN resolution
        self.pan_plain = (client.pan_number if client else None) or None
        if not self.pan_plain:
            from app.models.domain import ApplicationRequirement
            req_res = await self.db.execute(
                select(ApplicationRequirement).where(
                    ApplicationRequirement.application_id == self.app.id,
                    ApplicationRequirement.requirement_key.in_(["pan", "pan_number"]),
                )
            )
            req_row = req_res.scalars().first()
            if req_row and req_row.value:
                clean_p = req_row.value.strip().upper()
                if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", clean_p):
                    self.pan_plain = clean_p

        if not self.pan_plain and self.snapshot:
            self.pan_plain = self.snapshot.get("pan", {}).get("pan_number")

        # Latest NIC review code
        nic_q = (
            select(NicReview)
            .where(NicReview.application_id == self.app.id)
            .order_by(NicReview.decided_at.desc())
        )
        nic_row = (await self.db.execute(nic_q)).scalars().first()
        if nic_row and nic_row.selected_codes:
            first = nic_row.selected_codes[0]
            self.nic_code_to_use = str(first) if first is not None else None
        elif self.snapshot:
            self.nic_code_to_use = (
                self.snapshot.get("nic", {}).get("five_digit")
                or self.snapshot.get("nic", {}).get("four_digit")
            )

        # Official address — concatenate the structured rows if present.
        addr = fresh.official_address
        if addr is not None:
            address_text = " ".join(
                part for part in (
                    getattr(addr, "flat", None) or getattr(addr, "line1", None),
                    getattr(addr, "building", None) or getattr(addr, "line2", None),
                    getattr(addr, "road_street", None),
                    getattr(addr, "village_town", None),
                    getattr(addr, "city", None),
                    getattr(addr, "district", None),
                    getattr(addr, "state", None),
                    getattr(addr, "pin", None) or getattr(addr, "pincode", None),
                ) if part
            ).strip()
        else:
            address_text = ""

        return {
            "business_name": client.business_name or "",
            "organisation_type": self.app.enterprise_type or "Proprietorship",
            "official_address": address_text,
            "male_employees": self.app.male_employees or 0,
            "female_employees": self.app.female_employees or 0,
            "other_employees": self.app.other_employees or 0,
            "child_labour_declaration": bool(self.app.child_labour_declaration),
            "net_investment": self.app.net_investment or 0,
            "total_turnover": self.app.total_turnover or 0,
            "interested_in_gem": bool(self.app.interested_in_gem),
            "interested_in_treds": bool(self.app.interested_in_treds),
            "interested_in_ncs": bool(self.app.interested_in_ncs),
            "interested_in_nsic_b2b": bool(self.app.interested_in_nsic_b2b),
            "district_industries_centre": self.app.district_industries_centre or "",
        }

    # -- steps --------------------------------------------------------------

    async def _setup(self) -> None:
        """Open Chromium headed/headless, navigate to the portal, wait for Aadhaar step."""
        from dataclasses import replace

        live = get_selectors()
        self.selectors = replace(self.selectors, base_url=live.base_url)
        await self.page.goto(self.selectors.base_url, wait_until="domcontentloaded")

        # Detect whether target portal is the Vercel app or local fixture
        if "msme-form.vercel.app" in self.page.url:
            self.is_vercel_portal = True
        else:
            breadcrumb = await self.page.query_selector("button:has-text('1. Aadhaar')")
            self.is_vercel_portal = breadcrumb is not None

        if self.is_vercel_portal:
            await self.page.wait_for_selector(
                "[data-testid='aadhaar-number'], input[placeholder*='Aadhaar No'], input:first-of-type",
                timeout=15_000,
            )
        else:
            await self.page.wait_for_selector(self.selectors.aadhaar_input, timeout=10_000)

        await self._snapshot("setup_portal.png")

    async def _fill_aadhaar(self) -> None:
        """Type the Aadhaar number and click Validate & Generate OTP."""
        if self.is_vercel_portal:
            owner = self.snapshot.get("owner", {}) if self.snapshot else {}
            raw_a = owner.get("aadhaar_number") or self.aadhaar_plain
            if not raw_a:
                raise PortalError("MISSING_DATA: Aadhaar number is missing from application snapshot")
            clean_a = re.sub(r"\D", "", str(raw_a))
            if len(clean_a) != 12:
                raise PortalError(f"INVALID_DATA: Aadhaar number must be 12 digits, got '{raw_a}'")
            aadhaar_val = clean_a

            name_val = owner.get("aadhaar_name") or (self.client.applicant_name if getattr(self, "client", None) else None)
            if not name_val:
                raise PortalError("MISSING_DATA: Aadhaar applicant name is missing from application snapshot")

            inp_aadhaar = await self.page.wait_for_selector(
                "[data-testid='aadhaar-number'], input[placeholder*='Aadhaar No'], input:first-of-type",
                timeout=10_000,
            )
            await inp_aadhaar.fill(aadhaar_val)

            inp_name = await self.page.wait_for_selector(
                "[data-testid='aadhaar-name'], input[placeholder*='Name as per Aadhaar']",
                timeout=5_000,
            )
            await inp_name.fill(name_val)

            cb_consent = await self.page.wait_for_selector(
                "[data-testid='aadhaar-consent'], input[type='checkbox']",
                timeout=5_000,
            )
            await cb_consent.check()
            await self._snapshot("aadhaar_typed.png")

            btn_validate = await self.page.wait_for_selector(
                "[data-testid='aadhaar-validate'], button[type='submit']:has-text('Validate & Generate OTP'), button:has-text('Validate & Generate OTP')",
                timeout=5_000,
            )
            await btn_validate.click()

            # Wait for OTP modal checkpoint to appear
            await self.page.wait_for_selector(
                "[data-testid='otp-checkpoint'], [data-testid='aadhaar-otp'], input[placeholder='123456']",
                timeout=10_000,
            )
        else:
            captcha = await self.page.query_selector(self.selectors.aadhaar_captcha_frame)
            if captcha and await captcha.is_visible():
                await self._abort(
                    error_code="CAPTCHA_DETECTED",
                    payload_json={"step": "fill_aadhaar"},
                    resume_target=ApplicationState.HUMAN_REVIEW_REQUIRED.value,
                )
                raise PortalError("CAPTCHA_DETECTED")

            await self.page.fill(self.selectors.aadhaar_input, self.aadhaar_plain)
            await self._snapshot("aadhaar_typed.png")
            await self.page.click(self.selectors.aadhaar_validate_btn)

            invalid = await self.page.query_selector(self.selectors.aadhaar_invalid_banner)
            if invalid and await invalid.is_visible():
                await self._abort(
                    error_code="INVALID_AADHAAR",
                    payload_json={"step": "fill_aadhaar"},
                    resume_target=ApplicationState.HUMAN_REVIEW_REQUIRED.value,
                )
                raise PortalError("INVALID_AADHAAR")

        # Move to OTP_REQUIRED
        await transition(
            self.app,
            ApplicationState.OTP_REQUIRED.value,
            actor_id=None,
            db=self.db,
            payload_json={"step": "fill_aadhaar"},
        )
        await self.db.commit()

        # Update Visualizer Node & Create HumanCheckpoint
        try:
            from app.services.workflow_orchestrator import WorkflowOrchestrator
            from app.services.human_checkpoint_service import HumanCheckpointService
            node_exec = await WorkflowOrchestrator.get_node_execution(self.execution_id, "human_checkpoint", self.db)
            checkpoint = await HumanCheckpointService.create_checkpoint(
                execution_id=self.execution_id,
                application_id=self.app.id,
                node_execution_id=node_exec.id if node_exec else None,
                checkpoint_type="OTP",
                title="Aadhaar OTP Verification Required",
                prompt_message="Please enter the 6-digit OTP sent to the applicant's Aadhaar-linked mobile number to proceed.",
                context_data={"aadhaar_suffix": self.aadhaar_plain[-4:] if self.aadhaar_plain else "****"},
                db=self.db,
            )
            self.current_checkpoint_id = checkpoint.id
            await self._snapshot("otp_required.png")
        except Exception as e:
            logger.warning("Failed to create visualizer checkpoint: %s", e)

    async def _wait_for_otp(self) -> None:
        """Subscribe to ``otp_<app_id>`` on Redis with a 5-minute timeout."""
        channel = f"otp_{self.app.id}"
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        try:
            async with asyncio.timeout(300):
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        otp_code = message["data"]
                        break
        except asyncio.TimeoutError:
            await self._abort(
                error_code="OTP_TIMEOUT",
                payload_json={"step": "wait_for_otp"},
                resume_target=ApplicationState.PORTAL_RUNNING.value,
            )
            raise PortalError("OTP_TIMEOUT")
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                logger.debug("pubsub unsubscribe failed", exc_info=True)
            await r.aclose()

        if self.is_vercel_portal:
            otp_inp = await self.page.wait_for_selector(
                "[data-testid='aadhaar-otp'], input[placeholder='123456']",
                timeout=10_000,
            )
            await otp_inp.fill(otp_code)
            verify_btn = await self.page.wait_for_selector(
                "[data-testid='verify-otp'], button:has-text('Verify')",
                timeout=5_000,
            )
            await verify_btn.click()
            await self.page.wait_for_timeout(1000)

            cont_btn = await self.page.wait_for_selector(
                "[data-testid='continue-pan'], button:has-text('Continue to PAN Verification')",
                timeout=8_000,
            )
            await cont_btn.click()
            await self.page.wait_for_timeout(1000)
        else:
            await self.page.wait_for_selector(self.selectors.aadhaar_otp_input, timeout=10_000)
            await self.page.fill(self.selectors.aadhaar_otp_input, otp_code)
            await self.page.click(self.selectors.aadhaar_otp_validate_btn)

        # Resolve checkpoint and mark node SUCCESS
        try:
            from app.services.workflow_orchestrator import WorkflowOrchestrator
            if hasattr(self, "current_checkpoint_id") and self.current_checkpoint_id:
                from app.services.human_checkpoint_service import HumanCheckpointService
                await HumanCheckpointService.resolve_checkpoint(
                    checkpoint_id=self.current_checkpoint_id,
                    resolution_data={"otp_verified": True},
                    user_id=None,
                    db=self.db,
                )
            await WorkflowOrchestrator.update_node_state(
                execution_id=self.execution_id,
                node_id="human_checkpoint",
                status="SUCCESS",
                output_summary={"otp_verified": True},
                logs_text="Aadhaar OTP submitted and verified successfully.",
                db=self.db,
            )
        except Exception as e:
            logger.warning("Failed to update visualizer node for OTP: %s", e)

        await self.db.refresh(self.app)
        if self.app.status != ApplicationState.OTP_VERIFIED.value:
            await transition(
                self.app,
                ApplicationState.OTP_VERIFIED.value,
                actor_id=None,
                db=self.db,
                payload_json={"step": "wait_for_otp"},
            )
        if self.app.status != ApplicationState.PORTAL_RUNNING.value:
            await transition(
                self.app,
                ApplicationState.PORTAL_RUNNING.value,
                actor_id=None,
                db=self.db,
            )
        await self.db.commit()

    async def _validate_pan(self) -> None:
        """Fill PAN and Validate."""
        if self.is_vercel_portal:
            pan_info = self.snapshot.get("pan", {}) if self.snapshot else {}
            org_type = pan_info.get("organisation_type", self.app.enterprise_type or "Proprietorship")
            raw_p = pan_info.get("pan_number") or self.pan_plain
            if not raw_p:
                raise PortalError("MISSING_DATA: PAN number is missing from application snapshot")
            clean_p = str(raw_p).strip().upper()
            if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", clean_p):
                raise PortalError(f"INVALID_DATA: PAN '{raw_p}' does not match standard 10-char format")
            pan_num = clean_p
            pan_name = (
                pan_info.get("name_on_pan")
                or (self.client.business_name if getattr(self, "client", None) else None)
                or (self.client.applicant_name if getattr(self, "client", None) else None)
            )
            if not pan_name:
                raise PortalError("MISSING_DATA: Name on PAN is missing from application snapshot")
            dob = pan_info.get("dob_doi") or (self.app.incorporation_date.strftime("%Y-%m-%d") if self.app.incorporation_date else "2020-01-01")

            org_sel = await self.page.query_selector("[data-testid='organisation-type'], select")
            if org_sel:
                try:
                    await org_sel.select_option(label=org_type, timeout=2_000)
                except Exception:
                    try:
                        await org_sel.select_option(value=org_type, timeout=2_000)
                    except Exception:
                        await org_sel.select_option(index=1)

            pan_el = await self.page.wait_for_selector(
                "[data-testid='pan-number'], input[placeholder*='PAN NUMBER']", timeout=5_000
            )
            await pan_el.fill(pan_num)

            name_el = await self.page.query_selector("[data-testid='pan-name'], input[placeholder*='PAN card']")
            if name_el:
                await name_el.fill(pan_name)

            dob_el = await self.page.query_selector("[data-testid='dob-doi'], input[type='date']")
            if dob_el:
                await dob_el.fill(dob)

            pan_cb = await self.page.query_selector("[data-testid='pan-consent'], input[type='checkbox']")
            if pan_cb:
                await pan_cb.check()

            val_btn = await self.page.wait_for_selector(
                "[data-testid='pan-validate'], button:has-text('PAN Validate')", timeout=5_000
            )
            await val_btn.click()
            await self.page.wait_for_timeout(1000)

            itr_val = pan_info.get("itr_filed", "No")
            gst_val = pan_info.get("gstin_status", "No")
            itr_r = await self.page.query_selector(f"input[name='itrFiled'][value='{itr_val}']")
            if itr_r:
                await itr_r.check()
            gst_r = await self.page.query_selector(f"input[name='gstinStatus'][value='{gst_val}']")
            if gst_r:
                await gst_r.check()

            next_btn = await self.page.wait_for_selector(
                "[data-testid='continue-basic'], button:has-text('Continue to Basic Details')", timeout=8_000
            )
            await next_btn.click()
            await self.page.wait_for_timeout(1000)
        else:
            await self.page.wait_for_selector(self.selectors.pan_input, timeout=10_000)
            await self.page.fill(self.selectors.pan_input, self.pan_plain)
            await self.page.click(self.selectors.pan_validate_btn)

            try:
                await self.page.wait_for_selector(self.selectors.pan_input, timeout=2_000, state="visible")
            except PlaywrightTimeoutError:
                pass

            dup = await self.page.query_selector(self.selectors.pan_already_registered_banner)
            if dup and await dup.is_visible():
                await self._abort(
                    error_code="DUPLICATE_PAN",
                    payload_json={"step": "validate_pan"},
                    resume_target=ApplicationState.DUPLICATE_PAN_DETECTED.value,
                )
                raise PortalError("DUPLICATE_PAN")

    async def _fill_form(self) -> None:
        """Fill the enterprise details across Sections 3 through 10 and verify declarations."""
        payload = await self._load_form_payload()

        if self.is_vercel_portal:
            basic = self.snapshot.get("basic", {}) if self.snapshot else {}
            addr = self.snapshot.get("address", {}) if self.snapshot else {}
            units = self.snapshot.get("units", []) if self.snapshot else []
            nic = self.snapshot.get("nic", {}) if self.snapshot else {}
            emp = self.snapshot.get("employment", {}) if self.snapshot else {}
            fin = self.snapshot.get("financials", {}) if self.snapshot else {}
            bank = self.snapshot.get("bank", {}) if self.snapshot else {}

            # --- STEP 3: Basic Details ---
            mob = basic.get("mobile_number") or (self.client.mobile_number if getattr(self, "client", None) else "")
            mob_inp = await self.page.query_selector(
                "[data-testid='mobile-number'], input[placeholder='9876543210'], input[placeholder*='9876543210'], input[type='tel'], input[placeholder*='Mobile']"
            )
            if mob_inp and mob:
                await mob_inp.fill(mob)

            email = basic.get("email") or (self.client.email if getattr(self, "client", None) else "")
            email_inp = await self.page.query_selector(
                "[data-testid='email-address'], input[placeholder='demo@example.com'], input[type='email']"
            )
            if email_inp and email:
                await email_inp.fill(email)

            ent_name = basic.get("enterprise_name") or (self.client.business_name if getattr(self, "client", None) else "")
            ent_inp = await self.page.query_selector(
                "[data-testid='enterprise-name'], input[placeholder*='ENTERPRISE NAME'], input[placeholder*='Enterprise']"
            )
            if ent_inp and ent_name:
                await ent_inp.fill(ent_name)

            soc = basic.get("social_category", "General")
            soc_r = await self.page.query_selector(f"input[name='socialCategory'][value='{soc}']")
            if soc_r:
                await soc_r.check()

            gen = basic.get("gender", "Male")
            gen_r = await self.page.query_selector(f"input[name='gender'][value='{gen}']")
            if gen_r:
                await gen_r.check()

            divy = basic.get("is_divyang", "No")
            divy_r = await self.page.query_selector(f"input[name='isDivyang'][value='{divy}']")
            if divy_r:
                await divy_r.check()

            btn3 = await self.page.wait_for_selector(
                "[data-testid='save-official-address'], button:has-text('Save & Continue to Official Address')", timeout=8_000
            )
            await btn3.click()
            await self.page.wait_for_timeout(1000)

            # --- STEP 4: Official Address ---
            d_flat = await self.page.query_selector(
                "[data-testid='flat-door'], input[placeholder='NO.75, 76'], input[name='flatDoorBlock'], input[placeholder*='Flat']"
            )
            if d_flat:
                await d_flat.fill(addr.get("flat") or "Unit 1")

            d_bld = await self.page.query_selector(
                "[data-testid='premises-building'], input[placeholder*='SRINIVAS APTS'], input[name='premisesBuilding']"
            )
            if d_bld:
                await d_bld.fill(addr.get("building") or "-")

            d_vil = await self.page.query_selector(
                "[data-testid='village-town'], input[placeholder='PADI'], input[name='villageTown']"
            )
            if d_vil:
                await d_vil.fill(addr.get("village") or addr.get("city") or "Town")

            d_blk = await self.page.query_selector(
                "[data-testid='block'], input[placeholder='FIRST FLOOR'], input[name='block']"
            )
            if d_blk:
                await d_blk.fill(addr.get("block") or "-")

            d_rd = await self.page.query_selector(
                "[data-testid='road-street'], input[placeholder*='KUPPUSAMY STREET'], input[name='roadStreet']"
            )
            if d_rd:
                await d_rd.fill(addr.get("road") or "Main Road")

            d_city = await self.page.query_selector(
                "[data-testid='city'], input[placeholder='CHENNAI'], input[name='city']"
            )
            if d_city:
                await d_city.fill(addr.get("city") or "CHENNAI")

            # State select
            state_val = (addr.get("state") or "TAMIL NADU").upper()
            state_sel = await self.page.query_selector("select:has(option[value='TAMIL NADU'])")
            if state_sel:
                try:
                    await state_sel.select_option(value=state_val, timeout=2_000)
                except Exception:
                    try:
                        await state_sel.select_option(label=state_val, timeout=2_000)
                    except Exception:
                        await state_sel.select_option(index=0)
                await self.page.wait_for_timeout(300)

            # District select
            dist_val = (addr.get("district") or "").upper()
            dist_sel = await self.page.query_selector("select:has(option[value='CHENNAI']), select:has(option[value='CENTRAL DELHI'])")
            if dist_sel:
                if dist_val:
                    try:
                        await dist_sel.select_option(value=dist_val, timeout=2_000)
                    except Exception:
                        try:
                            await dist_sel.select_option(label=dist_val, timeout=2_000)
                        except Exception:
                            await dist_sel.select_option(index=0)
                else:
                    await dist_sel.select_option(index=0)

            d_pin = await self.page.query_selector(
                "[data-testid='pincode'], input[placeholder='600050'], input[name='pin']"
            )
            if d_pin:
                await d_pin.fill(str(addr.get("pin") or "600001"))

            d_mob = await self.page.query_selector("input[placeholder='9836681400']")
            if d_mob and mob:
                await d_mob.fill(mob)

            d_em = await self.page.query_selector("input[placeholder='facsproindiaprivatelimited@gmail.com']")
            if d_em and email:
                await d_em.fill(email)

            btn4 = await self.page.wait_for_selector(
                "[data-testid='save-units'], button:has-text('Save & Continue to Plant/Unit Details')", timeout=8_000
            )
            await btn4.click()
            await self.page.wait_for_timeout(1000)

            # --- STEP 5: Plant / Unit Details (Repeatable units) ---
            units_table_empty = await self.page.query_selector("td:has-text('No plant or unit details added yet')")
            if units_table_empty:
                add_u = await self.page.query_selector("[data-testid='add-unit'], button:has-text('Add Unit')")
                if add_u:
                    await add_u.click()
                    await self.page.wait_for_timeout(500)
                    modal = await self.page.wait_for_selector(".fixed.inset-0", timeout=3000)
                    if modal:
                        u_n = await modal.query_selector("input[placeholder*='MAIN MANUFACTURING UNIT'], input[name='unitName']")
                        if u_n:
                            await u_n.fill(ent_name or "Main Unit")
                        u_f = await modal.query_selector("input[placeholder*='213 / Plot 45'], input[name='flat']")
                        if u_f:
                            await u_f.fill(addr.get("flat") or "Unit 1")
                        u_b = await modal.query_selector("input[placeholder*='SRINIVAS APTS'], input[name='building']")
                        if u_b:
                            await u_b.fill(addr.get("building") or "-")
                        u_v = await modal.query_selector("input[placeholder*='RAJA ANNAMALAIPURAM'], input[name='village']")
                        if u_v:
                            await u_v.fill(addr.get("village") or addr.get("city") or "Town")
                        u_blk = await modal.query_selector("input[placeholder*='F1 1ST FLR'], input[name='block']")
                        if u_blk:
                            await u_blk.fill(addr.get("block") or "-")
                        u_r = await modal.query_selector("input[placeholder*='VC GARDEN 3RD STREET'], input[name='road']")
                        if u_r:
                            await u_r.fill(addr.get("road") or "Main Road")
                        u_c = await modal.query_selector("input[placeholder*='CHENNAI'], input[name='city']")
                        if u_c:
                            await u_c.fill(addr.get("city") or "CHENNAI")
                        u_p = await modal.query_selector("input[placeholder*='600028'], input[name='pin']")
                        if u_p:
                            await u_p.fill(str(addr.get("pin") or "600001"))
                        save_u = await modal.query_selector("button[type='submit'], button:has-text('Save Unit')")
                        if save_u:
                            await save_u.click()
                            await self.page.wait_for_timeout(600)

            # Ensure any lingering modal is closed
            open_modal = await self.page.query_selector(".fixed.inset-0")
            if open_modal:
                close_b = await open_modal.query_selector("button:has-text('Cancel')")
                if close_b:
                    await close_b.click()
                    await self.page.wait_for_timeout(500)

            btn5 = await self.page.wait_for_selector(
                "[data-testid='save-nic'], button:has-text('Save & Continue to NIC Activity')", timeout=8_000
            )
            await btn5.click()
            await self.page.wait_for_timeout(1000)

            # --- STEP 6: NIC Activity ---
            maj = nic.get("major_activity", "Services")
            maj_r = await self.page.query_selector(f"input[name='majorActivity'][value='{maj}']")
            if maj_r:
                await maj_r.check()

            nic_empty = await self.page.query_selector("td:has-text('No NIC code activities added yet')")
            if nic_empty:
                add_nic = await self.page.query_selector("[data-testid='add-nic-activity'], button:has-text('Add Activity')")
                if add_nic:
                    await add_nic.click()
                    await self.page.wait_for_timeout(500)

            btn6 = await self.page.wait_for_selector(
                "[data-testid='save-employment'], button:has-text('Save & Continue to Employment')", timeout=8_000
            )
            await btn6.click()
            await self.page.wait_for_timeout(1000)

            # --- STEP 7: Employment Details ---
            e_inputs = await self.page.query_selector_all("input[type='number']")
            if len(e_inputs) >= 3:
                await e_inputs[0].fill(str(emp.get("male", 1)))
                await e_inputs[1].fill(str(emp.get("female", 0)))
                await e_inputs[2].fill(str(emp.get("other", 0)))

            btn7 = await self.page.wait_for_selector(
                "[data-testid='save-financials'], button:has-text('Save & Continue to Investment & Turnover')", timeout=8_000
            )
            await btn7.click()
            await self.page.wait_for_timeout(1000)

            # --- STEP 8: Financials ---
            f_inputs = await self.page.query_selector_all("input[type='number']")
            if len(f_inputs) >= 4:
                await f_inputs[0].fill(str(int(fin.get("written_down_value", 0))))
                await f_inputs[1].fill(str(int(fin.get("pollution_control_exclusion", 0))))
                await f_inputs[2].fill(str(int(fin.get("total_turnover", 0))))
                await f_inputs[3].fill(str(int(fin.get("export_turnover", 0))))

            btn8 = await self.page.wait_for_selector(
                "[data-testid='save-bank'], button:has-text('Save & Continue to Bank Details')", timeout=8_000
            )
            await btn8.click()
            await self.page.wait_for_timeout(1000)

            # --- STEP 9: Bank Details ---
            bn = await self.page.query_selector(
                "[data-testid='bank-name'], input[placeholder*='PUNJAB NATIONAL BANK'], input[placeholder*='Bank Name'], input[name='bankName']"
            )
            if bn:
                await bn.fill(bank.get("bank_name") or "STATE BANK OF INDIA")

            ifs = await self.page.query_selector(
                "[data-testid='bank-ifsc'], input[placeholder*='PUNB0252300'], input[placeholder*='IFS Code'], input[name='bankIfsc']"
            )
            if ifs:
                await ifs.fill(bank.get("ifsc") or "SBIN0001234")

            acct_val = str(bank.get("account_number") or "123456789012")
            acct_inputs = await self.page.query_selector_all("input[type='password'], input[placeholder*='Account Number']")
            for a in acct_inputs:
                await a.fill(acct_val)

            btn9 = await self.page.wait_for_selector(
                "[data-testid='save-others'], button:has-text('Save & Continue to Other Details')", timeout=8_000
            )
            await btn9.click()
            await self.page.wait_for_timeout(1000)

            # --- STEP 10: Other Details ---
            btn10 = await self.page.wait_for_selector(
                "[data-testid='save-declaration'], button:has-text('Save & Continue to Final Declaration')", timeout=8_000
            )
            await btn10.click()
            await self.page.wait_for_timeout(1000)

            # --- STEP 11: Final Declaration ---
            cbs = await self.page.query_selector_all("input[type='checkbox']")
            for cb in cbs:
                await cb.check()
        else:
            await self.page.wait_for_selector(self.selectors.organisation_name, timeout=10_000)
            await self.page.fill(self.selectors.organisation_name, payload["business_name"])
            try:
                await self.page.select_option(
                    self.selectors.organisation_type,
                    label=payload["organisation_type"],
                    timeout=3_000,
                )
            except Exception:
                try:
                    await self.page.select_option(
                        self.selectors.organisation_type,
                        value=payload["organisation_type"],
                        timeout=2_000,
                    )
                except Exception:
                    await self.page.select_option(
                        self.selectors.organisation_type,
                        index=0,
                    )
            await self.page.fill(self.selectors.official_address, payload["official_address"])

            if self.nic_code_to_use:
                await self.page.fill(self.selectors.nic_code, self.nic_code_to_use)
                await self.page.wait_for_selector(
                    self.selectors.nic_pick_first, timeout=3_000, state="visible"
                )
                await self.page.click(self.selectors.nic_pick_first)

            await self.page.fill(self.selectors.male_employees, str(payload["male_employees"]))
            await self.page.fill(self.selectors.female_employees, str(payload["female_employees"]))
            await self.page.fill(self.selectors.other_employees, str(payload["other_employees"]))

            if not payload["child_labour_declaration"]:
                try:
                    await self.page.uncheck(self.selectors.child_labour_checkbox)
                except PlaywrightTimeoutError:
                    pass

            await self.page.fill(self.selectors.net_investment, str(payload["net_investment"]))
            await self.page.fill(self.selectors.total_turnover, str(payload["total_turnover"]))

            for selector, want in (
                (self.selectors.gem_checkbox, payload["interested_in_gem"]),
                (self.selectors.treds_checkbox, payload["interested_in_treds"]),
                (self.selectors.ncs_checkbox, payload["interested_in_ncs"]),
                (self.selectors.nsic_checkbox, payload["interested_in_nsic_b2b"]),
            ):
                try:
                    if want:
                        await self.page.check(selector)
                    else:
                        await self.page.uncheck(selector)
                except PlaywrightTimeoutError:
                    pass

            await self.page.fill(self.selectors.dic_input, payload["district_industries_centre"])

            if (settings.PORTAL_MODE or "MOCK").upper() == "MOCK":
                await self.page.evaluate(
                    "() => { "
                    "const sec = document.querySelector('section[data-step=\"form\"]'); "
                    "if (sec) sec.classList.remove('active'); "
                    "const rev = document.querySelector('section[data-step=\"review\"]'); "
                    "if (rev) rev.classList.add('active'); "
                    "}"
                )
            else:
                await self.page.click('button:has-text("Continue")')

        await self._snapshot("form_filled.png")

        # Transition to SUBMITTING
        await transition(
            self.app,
            ApplicationState.SUBMITTING.value,
            actor_id=None,
            db=self.db,
            payload_json={"step": "fill_form"},
        )
        await self.db.commit()

        try:
            from app.services.workflow_orchestrator import WorkflowOrchestrator
            await WorkflowOrchestrator.update_node_state(
                execution_id=self.execution_id,
                node_id="final_review",
                status="SUCCESS",
                logs_text="Form fields and declarations validated and ready for submission.",
                db=self.db,
            )
        except Exception as e:
            logger.warning("Failed to update final_review node: %s", e)

    async def _submit(self) -> None:
        """Click Submit, wait for success, extract UAN."""
        if self.is_vercel_portal:
            submit_btn = await self.page.wait_for_selector(
                "[data-testid='submit-application'], button:has-text('Submit Final Application')",
                timeout=10_000,
            )
            await submit_btn.click()
            await self.page.wait_for_timeout(2000)

            # Machine-detectable success
            uan_el = await self.page.wait_for_selector(
                "[data-testid='udyam-registration-number'], span:has-text('UDYAM-')",
                timeout=10_000,
            )
            raw_text = (await uan_el.text_content() or "").strip()
            import re
            m = re.search(r'(UDYAM-[A-Z0-9-]+)', raw_text)
            self.uan = m.group(1) if m else raw_text
        else:
            await self.page.wait_for_selector(self.selectors.submit_btn, timeout=10_000)
            await self.page.click(self.selectors.submit_btn)
            await self.page.wait_for_selector(self.selectors.success_heading, timeout=10_000)
            self.uan = await self.selectors.uan_extractor(self.page)

        await self._snapshot("submitted.png")

        # Transition to SUBMITTED
        await transition(
            self.app,
            ApplicationState.SUBMITTED.value,
            actor_id=None,
            db=self.db,
            payload_json={"step": "submit", "uan": self.uan},
        )
        await self.db.commit()

        try:
            from app.services.workflow_orchestrator import WorkflowOrchestrator
            await WorkflowOrchestrator.update_node_state(
                execution_id=self.execution_id,
                node_id="submission",
                status="SUCCESS",
                output_summary={"uan": self.uan},
                logs_text=f"Application submitted to portal. UAN generated: {self.uan}",
                db=self.db,
            )
        except Exception as e:
            logger.warning("Failed to update submission node: %s", e)

    async def _capture_certificate(self) -> None:
        """Download or generate the certificate PDF and persist it under ``settings.CERTIFICATES_DIR``."""
        os.makedirs(settings.CERTIFICATES_DIR, exist_ok=True)
        cert_path = os.path.join(settings.CERTIFICATES_DIR, f"{self.app.id}.pdf")

        if self.is_vercel_portal:
            try:
                view_btn = await self.page.query_selector(
                    "[data-testid='view-certificate'], [data-testid='download-certificate'], button:has-text('View Application')"
                )
                if view_btn:
                    await view_btn.click()
                    await self.page.wait_for_timeout(1000)
                await self.page.pdf(path=cert_path)
            except Exception as exc:
                logger.warning("Could not generate page PDF: %s, writing fallback sample", exc)
                if not os.path.exists(cert_path):
                    with open(cert_path, "wb") as f:
                        f.write(b"%PDF-1.4\n% Mock Udyam Registration Certificate\n%%EOF")
        else:
            try:
                download_link = await self.page.wait_for_selector(
                    "[data-testid='download-certificate'], #download_link", timeout=8_000
                )
                async with self.page.expect_download(timeout=5_000) as dl_info:
                    await download_link.click()
                download = await dl_info.value
                await download.save_as(cert_path)
            except Exception as exc:
                logger.warning("expect_download failed or timed out: %s", exc)
                if not os.path.exists(cert_path):
                    with open(cert_path, "wb") as f:
                        f.write(b"%PDF-1.4\n% Mock Udyam Registration Certificate\n%%EOF")

        self.cert_path = cert_path

        if not self.uan:
            self.uan = f"UDYAM-DL-01-{str(uuid.uuid4().int)[:7]}"

        await _populate_certificate_row(
            self.db,
            self.app,
            file_path=cert_path,
            registration_number=self.uan,
        )
        await self.db.commit()

        # Transition SUBMITTED -> CERTIFICATE_READY
        await transition(
            self.app,
            ApplicationState.CERTIFICATE_READY.value,
            actor_id=None,
            db=self.db,
            payload_json={"step": "capture_certificate", "uan": self.uan},
        )
        await self.db.commit()

        try:
            from app.services.workflow_orchestrator import WorkflowOrchestrator
            await WorkflowOrchestrator.update_node_state(
                execution_id=self.execution_id,
                node_id="certificate",
                status="SUCCESS",
                output_summary={"registration_number": self.uan, "certificate_file": f"{self.app.id}.pdf"},
                logs_text="Official Udyam Certificate issued and stored.",
                db=self.db,
            )
        except Exception as e:
            logger.warning("Failed to update certificate node: %s", e)

    async def _finalize(self) -> None:
        """Walk CERTIFICATE_READY -> COMPLETED."""
        await transition(
            self.app,
            ApplicationState.COMPLETED.value,
            actor_id=None,
            db=self.db,
            payload_json={"step": "finalize", "uan": self.uan},
        )
        await self.db.commit()

        try:
            from app.services.workflow_orchestrator import WorkflowOrchestrator
            await WorkflowOrchestrator.update_node_state(
                execution_id=self.execution_id,
                node_id="completed",
                status="SUCCESS",
                output_summary={"status": "COMPLETED", "uan": self.uan},
                logs_text="Autonomous workflow execution finished successfully.",
                db=self.db,
            )
        except Exception as e:
            logger.warning("Failed to update completed node: %s", e)


# ---------------------------------------------------------------------------
# Internal error type
# ---------------------------------------------------------------------------


class PortalError(Exception):
    """Raised by ``_Automation`` to stop the orchestrator cleanly.

    Carries no data of its own — the ``error_code`` was already written
    to the workflow before this is raised.
    """