# Phase 07 — Reviews + Certificates

**Goal:** Persist NIC review decisions, final review signoffs, and serve the registration certificate PDF. Today these tables exist but nothing writes to them.

---

## Pre-requisites

Phases 01, 05, 06 complete. State machine writes `WorkflowEvent` (Phase 03). RBAC enforced.

---

## Scope (in)

### NIC Review

1. **New table `nic_reviews`** — `(id UUID, application_id FK, reviewer_id FK→users, selected_codes JSONB, justification TEXT, decided_at TIMESTAMP, decision TEXT check (decision in ('APPROVE','REJECT','OVERRIDE')))`. Alembic migration.
2. **`POST /api/v1/applications/{id}/nic/approve`** — replaces the existing handler. Body: `{ selected_codes: string[], justification: string }`. Writes a `NicReview` row with `decision='APPROVE'`. Transitions `NIC_REVIEW → READY_FOR_PORTAL`. RBAC: REVIEWER_AUDITOR+.
4. **`POST /api/v1/applications/{id}/nic/reject`** — new. Body: `{ justification: string }`. Writes `NicReview` with `decision='REJECT'`. Transitions `NIC_REVIEW → DATA_VERIFICATION` (resolve path). RBAC: REVIEWER_AUDITOR+.

### Final Review

4. **New table `final_reviews`** — `(id UUID, application_id FK, reviewer_id FK→users, kyc_confirmed BOOL, signoff_method TEXT, declared_at TIMESTAMP, remarks TEXT)`. Alembic migration.
5. **`POST /api/v1/applications/{id}/final-review`** — new. Body: `{ kyc_confirmed: bool, signoff_method: "DIGITAL_SIGNATURE" | "AADHAAR_OTP", remarks: string }`. Writes `FinalReview` row. Transitions `HUMAN_REVIEW → APPROVED`. RBAC: REVIEWER_AUDITOR+.

### Certificate

6. **`GET /api/v1/applications/{id}/certificate`** — new. Returns the registration certificate PDF (`application/pdf`).
   - If `applications.status == COMPLETED` and `certificates` row exists with `pdf_path` set, stream the file from `storage/certificates/<application_id>.pdf`.
   - Else (the application hasn't been fully submitted yet): return 409 with `{ "message": "Application not yet completed" }`.
   - RBAC: any role with branch scope.
7. **Populate the `certificates` table** — when an application reaches `SUBMITTED` (via the submit endpoint, Phase 05), generate a placeholder PDF (Jinja2 template + weasyprint or `fpdf2`) and persist `pdf_path`. The portal certificate is captured by the Playwright worker (Phase 09) and replaces this placeholder if present.

---

## Scope (out)

- Do NOT build a fancy certificate UI (Phase 11).
- Do NOT implement digital signatures — placeholder suffices.

---

## Deliverables checklist

- [ ] `backend/app/models/domain.py` — `NicReview`, `FinalReview` models.
- [ ] `backend/alembic/versions/<hash>_nic_final_reviews.py` — migration.
- [ ] `backend/app/api/applications.py` — `/nic/approve` writes `NicReview`; `/nic/reject` added.
- [ ] `backend/app/api/applications.py` or `workflow.py` — `/final-review` endpoint added.
- [ ] `backend/app/api/certificates.py` — new file; `GET /certificate` endpoint.
- [ ] `backend/app/services/certificate_generator.py` — placeholder PDF generator (`fpdf2` already in requirements).
- [ ] `backend/tests/test_reviews.py` — NIC approve + reject; final-review; certificate 200 + 409.
- [ ] `backend/tests/test_certificates.py` — placeholder PDF generated and served.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`
2. `alembic upgrade head` — migration applies cleanly.
3. `pytest backend/tests/test_reviews.py -v` — green.
4. `pytest backend/tests/test_certificates.py -v` — green.
5. `pytest backend/tests/ -q` — full suite green.
6. Manual: as REVIEWER_AUDITOR, approve NIC → assert `NicReview` row exists + application is in `READY_FOR_PORTAL`.
7. Manual: same, reject → assert row + application back in `DATA_VERIFICATION`.
8. Manual: GET `/certificate` for an in-progress app → 409.
9. Manual: move an app to COMPLETED → GET `/certificate` → 200 + valid PDF.

---

## Definition of done

- `NicReview` + `FinalReview` tables persist every decision.
- Every approve/reject/signoff writes both a state-machine transition AND a review row.
- `certificates` table is populated at `SUBMITTED`.
- Certificate endpoint serves the PDF.
- All tests pass; no regression.

---

## CONTINUATION PROMPT — start Phase 08

```
Starting Phase 08 of the AINCURU × TAXLA remediation. Phase 07 is complete: NicReview +
FinalReview tables exist with proper endpoints; Certificate table is populated when an
application reaches COMPLETED; certificate PDF endpoint returns the file.

Read the full plan: documents/implementation phases/phase-08-trigger-action.md

Goal: Build the trigger-action system per docs/11_trigger_action_system.md. Currently
the `triggers` + `actions` tables exist in spec but not in code. Add:
- Backend: `triggers` and `actions` tables (per spec); trigger router with CRUD;
  dispatcher that listens to state-machine transitions (every `transition()` call must
  publish to Redis `taxla:events`); action runner (HTTP webhook / email / shell /
  Playwright / state-transition actions); new `backend/app/services/triggers.py`
  matching engine; `backend/tests/test_triggers.py`.
- Frontend: `/automations` page (new — list + create triggers); Zustand store for
  trigger definitions.
- Seed: trigger "DOCUMENT_UPLOADED → RunOCR" auto-created on app boot if absent;
  trigger "DATA_VERIFICATION_APPROVED → SuggestNIC" auto-created; trigger
  "OTP_REQUIRED → NotifyOperator" auto-created.

After Phase 08 verification, paste the Phase 09 continuation prompt.

---

PHASE 09 CONTINUATION PROMPT:

Starting Phase 09 of the AINCURU × TAXLA remediation. Phase 08 is complete: trigger-
action system is live — every state transition publishes to Redis, the dispatcher matches
triggers, the runner executes actions. Seed triggers (DOCUMENT_UPLOADED→RunOCR,
DATA_VERIFICATION_APPROVED→SuggestNIC, OTP_REQUIRED→NotifyOperator) are auto-installed.
CRUD endpoints + /automations dashboard exist.

Read the full plan: documents/implementation phases/phase-09-udyam-portal.md

Goal: Make the Playwright portal automation actually do something per
documents/21_udyam_portal_automation.md. Currently worker/playwright_agent.py:48 just
navigates to the portal then transitions to OTP_REQUIRED. It never fills the Aadhaar
form, never validates Aadhaar, never submits. This phase replaces the mock-portal
selectors with real ones (or, if you don't have portal access, with a recorded fixture)
and wires the OTP handoff properly:
- Aadhaar entry: page.fill('input[name="aadhaar"]', app.aadhaar). Press Validate. Wait
  for OTP_REQUIRED state in DB. The operator types OTP in UI. Worker reads OTP from
  Redis (pub/sub) and pastes into the portal.
- PAN entry: after Aadhaar OTP succeeds, page.fill('input[name="pan"]', app.pan).
  Press Validate. Worker polls for the next state.
- Form fill: organisation name, address, NIC code, employment, investment + turnover
  fields, GeM/TReDS/NCS opt-ins.
- Final submission: click "Submit". Worker waits for the success page; parses
  application number; transitions SUBMITTED → CERTIFICATE_READY → COMPLETED. PDF
  certificate downloaded to storage/certificates/ and Certificate row updated.
- Error matrix: portal down → EXCEPTION (PORTAL_DOWN); CAPTCHA → EXCEPTION
  (CAPTCHA_DETECTED); Aadhaar mismatch → HUMAN_REVIEW_REQUIRED; PAN duplicate →
  DUPLICATE_PAN_DETECTED.
- All selectors live in backend/app/services/portal_selectors.py so they can be
  swapped per-environment (real portal vs. mock portal fixture).
- New backend/tests/test_portal_automation.py covers each transition with a recorded
  trace.
```