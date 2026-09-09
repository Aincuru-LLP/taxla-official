# Phase 08 — Trigger-Action System

**Goal:** Build the trigger-action system per `documents/11_trigger_action_system.md`. The spec describes triggers (`DOCUMENT_UPLOADED → RunOCR`, `DATA_VERIFICATION_APPROVED → SuggestNIC`) but no code exists today. After this phase, every state transition automatically fires any matching triggers and the actions execute.

---

## Pre-requisites

Phases 01, 03, 05 complete. State machine writes events (Phase 03). RBAC enforced.

---

## Scope (in)

### Backend

1. **New tables** — Alembic migration:
   - `triggers (id UUID, branch_id UUID FK→branches, name TEXT, event_pattern TEXT, condition_json JSONB, is_active BOOL, created_by UUID FK→users, created_at TIMESTAMP, updated_at TIMESTAMP)`.
   - `actions (id UUID, trigger_id UUID FK→triggers ON DELETE CASCADE, type TEXT, config_json JSONB, sort_order INT, is_active BOOL)`.
2. **`transition()` publishes events** — `backend/app/core/state_machine.py`. After a successful transition (audit log written), publish `{ "event": "STATE_TRANSITIONED", "application_id": ..., "from": ..., "to": ..., "payload": ... }` to Redis channel `taxla:events`.
3. **Subscriber / dispatcher** — `backend/app/services/triggers.py` + `backend/worker/dispatcher.py`. Worker subscribes to `taxla:events`, matches each event against active triggers (`event_pattern` is a glob like `STATE_TRANSITIONED.*.NIC_REVIEW` or a literal `DOCUMENT_UPLOADED`), evaluates `condition_json` against the event payload, and enqueues actions.
4. **Action runner** — `backend/app/services/action_runner.py`. Supports:
   - `HTTP_WEBHOOK` — POST config_json["url"] with the event payload, optional HMAC signature.
   - `EMAIL` — send config_json["to"] (via SendGrid or SMTP; use what's already configured).
   - `SHELL` — run config_json["command"] (off by default; gated behind SUPER_ADMIN role on the trigger).
   - `STATE_TRANSITION` — call `transition(application_id, config_json["to_state"])` directly. This is how "DOCUMENT_UPLOADED → RunOCR" works: the action is `STATE_TRANSITION` to `PROCESSING`, which itself has a trigger "PROCESSING → OCR_DONE" that calls the OCR worker. (Chaining is fine — events re-publish.)
   - `PLAYWRIGHT` — enqueue a Playwright job (used by Phase 09).
5. **Trigger CRUD** — `backend/app/api/triggers.py`:
   - `GET /api/v1/triggers` — list active triggers for branch.
   - `POST /api/v1/triggers` — create trigger + its actions in one body. RBAC: BRANCH_ADMIN+.
   - `PATCH /api/v1/triggers/{id}` — toggle / edit. RBAC: BRANCH_ADMIN+.
   - `DELETE /api/v1/triggers/{id}` — soft-delete. RBAC: BRANCH_ADMIN+.
6. **Seed triggers on boot** — `backend/app/services/trigger_seeds.py`. On app startup, ensure these exist (idempotent):
   - `DOCUMENT_UPLOADED → STATE_TRANSITION to PROCESSING` (kicks off OCR).
   - `STATE_TRANSITIONED.*.NIC_REVIEW → EMAIL to reviewers` (notify there's work to review).
   - `STATE_TRANSITIONED.*.OTP_REQUIRED → EMAIL to operator` (notify OTP is needed).
7. **Tests** — `backend/tests/test_triggers.py`. One per match-pattern type. Verify the dispatcher picks up events from Redis, filters by condition_json, and enqueues actions. Mock the actual action execution.

### Frontend

8. **`/automations` page** — `frontend/src/app/automations/page.tsx`. List existing triggers; "Create trigger" modal with event pattern dropdown + actions repeater. Wired to the API.
9. **Zustand store** — `frontend/src/stores/triggersStore.ts`. Triggers list cache.

---

## Scope (out)

- Do NOT build a visual rule builder (JSON config is fine for MVP).
- Do NOT add trigger versioning / audit (just `updated_at`).

---

## Deliverables checklist

- [ ] `backend/app/models/domain.py` — `Trigger`, `Action` models.
- [ ] `backend/alembic/versions/<hash>_triggers_actions.py` — migration.
- [ ] `backend/app/core/state_machine.py` — `transition()` publishes to `taxla:events`.
- [ ] `backend/app/services/triggers.py` — pattern matcher + dispatcher entry point.
- [ ] `backend/app/services/action_runner.py` — 5 action types implemented.
- [ ] `backend/worker/dispatcher.py` — ARQ job / Redis subscriber.
- [ ] `backend/app/api/triggers.py` — CRUD router.
- [ ] `backend/app/services/trigger_seeds.py` — boot-time seed.
- [ ] `backend/app/main.py` — lifespan calls `trigger_seeds.run()`.
- [ ] `backend/tests/test_triggers.py` — dispatcher + action runner tests.
- [ ] `frontend/src/app/automations/page.tsx` — list + create UI.
- [ ] `frontend/src/stores/triggersStore.ts` — Zustand store.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`
2. `alembic upgrade head`
3. `pytest backend/tests/test_triggers.py -v` — green.
4. `pytest backend/tests/ -q` — full suite green.
5. Start backend + worker. Confirm seed triggers exist (`GET /api/v1/triggers`).
6. Manually transition an application. Confirm `taxla:events` channel gets a message (use `redis-cli SUBSCRIBE taxla:events` in a separate terminal).
7. Create a test trigger with an action that calls `https://webhook.site/<uuid>`. Trigger it. Confirm webhook.site receives the call.
8. Frontend: visit `/automations`, confirm 3 seeded triggers listed; create a 4th; delete it.

---

## Definition of done

- Every state transition publishes to `taxla:events`.
- Dispatcher matches + executes actions.
- 3 seed triggers installed automatically.
- CRUD + dashboard work.
- All tests pass.

---

## CONTINUATION PROMPT — start Phase 09

```
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

After Phase 09 verification, paste the Phase 10 continuation prompt.

---

PHASE 10 CONTINUATION PROMPT:

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
```