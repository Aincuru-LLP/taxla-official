# Phase 09 — Real Udyam Portal Automation

**Goal:** Make `worker/playwright_agent.py` actually fill the Aadhaar form, handle the OTP handoff, fill the PAN, complete the rest of the registration form, and submit on `udyamregistration.gov.in`. Today it just navigates to the portal and transitions to `OTP_REQUIRED` — nothing else.

---

## Pre-requisites

Phases 01, 03, 05, 06, 08 complete. State machine + RBAC + auth + triggers ready. `PortalAutomationService` class exists.

---

## Scope (in)

1. **New file `backend/app/services/portal_selectors.py`** — centralized selector registry. Two modes:
   - `LIVE` (default): selectors for the real `udyamregistration.gov.in` portal.
   - `MOCK`: selectors for a recorded local fixture (`tests/fixtures/mock_portal/index.html`). Selected via `PORTAL_MODE` env var.
2. **Rewrite `backend/worker/playwright_agent.py`** — replace the stub navigation:
   - **Navigate** to `https://udyamregistration.gov.in/UA/UA_Registration.aspx` (or the mock URL).
   - **Aadhaar step:** `page.fill('input[name="aadhaar"]', app.aadhaar_number)`. Press "Validate & Generate OTP". Transition `PORTAL_RUNNING → AADHAAR_OTP` (NEW state added per Phase 03) and wait.
   - **OTP handoff:** subscribe to Redis `otp_{application_id}` channel. Operator posts OTP via `POST /api/v1/applications/{id}/otp` (Phase 05 endpoint). The OTP endpoint publishes to that channel. Worker types OTP into the portal page. Press "Validate".
   - **PAN step:** `page.fill('input[name="pan"]', app.pan)`. Press "Validate PAN". If portal says "PAN already registered" → transition to `DUPLICATE_PAN_DETECTED` and exit.
   - **Form fill:** organisation name, type of organisation, official address, NIC code (selected by reviewer in Phase 07), employment count, investment + turnover fields, GeM / TReDS / NCS / NSIC opt-ins, DIC declaration, child-labour declaration. Each field's selector lives in `portal_selectors.py`.
   - **Final submit:** press "Submit". Wait for the success screen. Parse the Udyam Registration Number (`UAN`) from the response HTML. Transition `SUBMITTING → SUBMITTED → CERTIFICATE_READY`.
   - **Certificate download:** the portal's success page has a "Download Certificate" link. `page.expect_download()`. Save to `storage/certificates/<application_id>.pdf`. Update the `certificates` row.
   - **Final transition:** `CERTIFICATE_READY → COMPLETED`.
3. **Error matrix** — exhaustive handlers:
   - Portal returns 5xx / connection refused → `EXCEPTION` + `error_code = PORTAL_DOWN` + `resume_target = PORTAL_RUNNING`.
   - CAPTCHA appears → `EXCEPTION` + `error_code = CAPTCHA_DETECTED` + `resume_target = HUMAN_REVIEW_REQUIRED`.
   - Aadhaar validation says "Invalid Aadhaar" → `HUMAN_REVIEW_REQUIRED` (operator re-uploads the Aadhaar document).
   - PAN validation says "PAN already registered" → `DUPLICATE_PAN_DETECTED` (existing state from Phase 03).
   - Timeout waiting for any element (10s default) → `EXCEPTION` + `error_code = PORTAL_TIMEOUT` + screenshot saved to `storage/debug/<application_id>.png`.
4. **Use `transition()` everywhere** — no direct mutation of `app.status`. Phase 03 already fixed this; preserve that.
5. **Tests** — `backend/tests/test_portal_automation.py`. Use `MOCK` mode + Playwright's `headless=False` for local. Cover each step: aadhaar fill, OTP receive, PAN fill, form fill, submit, certificate download. Each transition's `WorkflowEvent` should be asserted.

---

## Scope (out)

- Do NOT attempt to solve CAPTCHAs (humans do).
- Do NOT add a stealth / anti-detection layer — the portal blocks bots by design; humans must intervene via the OTP handoff anyway.

---

## Deliverables checklist

- [ ] `backend/app/services/portal_selectors.py` — selector registry with LIVE + MOCK variants.
- [ ] `backend/worker/playwright_agent.py` — fully rewritten; all selectors via the registry; `transition()` for every state change.
- [ ] `backend/app/core/config.py` — `PORTAL_MODE` (LIVE / MOCK) env var; `PORTAL_BASE_URL`.
- [ ] `backend/tests/fixtures/mock_portal/index.html` — recorded fixture for MOCK mode.
- [ ] `backend/tests/test_portal_automation.py` — full step coverage.
- [ ] `storage/certificates/` — populated when an application completes.
- [ ] `storage/debug/` — populated on failures.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`
2. `pytest backend/tests/test_portal_automation.py -v` — green in MOCK mode.
3. `pytest backend/tests/ -q` — full suite green.
4. Manual: create an application, upload docs, approve NIC, start automation. Worker opens a browser, fills Aadhaar, halts at OTP. Operator enters OTP. Worker continues, fills PAN, fills form, submits, downloads cert. Application reaches COMPLETED.
5. Manual: intentionally trigger each error case. Confirm the correct `error_code` + state + screenshot.
6. Confirm `storage/certificates/<application_id>.pdf` exists after completion and is valid PDF.

---

## Definition of done

- Real portal flow (Aadhaar → OTP → PAN → form → submit → certificate download) runs end-to-end in MOCK mode.
- LIVE mode selectors documented; safe to attempt against the real portal (but you should run it in a sandboxed account first).
- Error matrix handled with explicit state transitions + screenshots.
- No direct mutation of `app.status` anywhere.
- All tests pass.

---

## CONTINUATION PROMPT — start Phase 10

```
Starting Phase 10 of the AINCURU × TAXLA remediation. Phase 09 is complete: the Playwright
worker now fills the Aadhaar form, validates Aadhaar, handles the OTP handoff, fills the
PAN, completes the rest of the form, submits, and downloads the certificate. Selectors
live in portal_selectors.py so the real portal and a fixture mock are swappable. Error
matrix is implemented and tested.

Read the full plan: documents/implementation phases/phase-10-nic-expansion.md

Goal: Expand NIC dataset from ~94 hand-curated codes to the full ~1,300 codes per the
official NIC 2008 handbook (docs/14_nic_classification.md).
- Source: parse the official NIC-2008 PDF (already available in scripts/parse_nic_pdf.py
  — it currently outputs 94 codes). Fix the duplicate fitz/pymupdf import (Phase 01),
  then re-parse the full handbook. Expected output: data/nic_2008.json with all classes,
  sub-classes, groups, and descriptions.
- Re-run scripts/generate_nic_data.py to regenerate data/nic_2008.json.
- Validate the dataset: every code matches the regex ^[0-9]{2,5}$, every code has a
  description, no duplicates.
- Vector tier (Phase 02's nic_service.py): rebuild embeddings. Use sentence-transformers
  or Ollama's nomic-embed-text. Store in a small FAISS index keyed by NIC code.
- Keyword tier: expand keyword list to include all class-level + group-level
  descriptions from the new dataset.
- Tests: backend/tests/test_nic_classification.py — assert at least 1,000 distinct codes
  loadable; assert the vector index is built; assert a smoke test of "manufacturing
  paper" → finds the right NIC code in top-3.

After Phase 10 verification, paste the Phase 11 continuation prompt.

---

PHASE 11 CONTINUATION PROMPT:

Starting Phase 11 of the AINCURU × TAXLA remediation. Phase 10 is complete: NIC dataset
covers the full ~1,300 codes from the official NIC-2008 handbook. Vector tier uses a
local FAISS index. Keyword tier matches against class-level descriptions. Top-3 hit
rate ≥90% on the smoke tests.

Read the full plan: documents/implementation phases/phase-11-frontend-spec.md

Goal: Frontend spec compliance per docs/06_tech_stack.md, docs/29_frontend_architecture.md,
docs/33_audit_timeline.md. This is the big frontend phase. Tackle:
1. Install + adopt React Query, Zustand, React Hook Form, Zod. Replace raw useState/
   useEffect data fetching with React Query hooks (typed). Replace ad-hoc forms with
   RHF + Zod schemas.
2. Convert 5 .jsx components to .tsx with proper prop interfaces: Sidebar.tsx,
   KanbanDashboard.tsx, ApplicationWorkspace.tsx, NICReviewPanel.tsx,
   OTPInputModal.tsx.
3. Build the missing domain molecules: DocumentViewer.tsx, ExtractedDataForm.tsx,
   WorkflowStepper.tsx, StatusBadge.tsx, ConfidenceIndicator.tsx, DataField.tsx.
4. Replace ApplicationWorkspace.tsx's placeholder audit-log div with a real timeline
   that fetches /api/v1/applications/{id}/audit and /api/v1/applications/{id}/
   workflow-events.
5. Resolve dark/light fragmentation — pick dark-first (per spec), update
   applications/[id] page + settings page to use the dark theme.
6. Add the missing 3 dashboard routes (Automations, Workflows, AI Agents) — at least
   functional placeholder pages that show data the backend now exposes.
7. Add a 404 page, breadcrumbs, user menu in Sidebar (Logout was Phase 06).
8. Add a shared useWebSocket hook (auth'd, debounced, per-message-type routing) used by
   both KanbanDashboard and ApplicationWorkspace. The current refetch storm must go.
9. Make Settings tabs real: each of the 5 tabs implements its save handler.
10. Add accessibility: labels for every input, aria-labels for icon buttons.

After Phase 11 verification, paste the Phase 12 continuation prompt.
```