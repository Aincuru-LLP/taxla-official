# Phase 04 — Validation Engine — Confidence Branching

**Goal:** Make `validation_engine.py` actually branch on OCR confidence per `documents/19_document_processing.md`. End state: HIGH-confidence extractions auto-proceed to NIC review; MEDIUM-confidence flag for reviewer attention; LOW-confidence forces manual review. Plus real format validators for PAN, Aadhaar, IFSC, GSTIN, mobile, email, pincode.

---

## Pre-requisites

Phases 01 + 02 complete. Phase 03 strongly recommended (so `transition()` writes events; you want confidence-based branching to be auditable).

---

## Scope (in)

1. **Confidence-based branching** — `backend/app/services/validation_engine.py:38` currently calls `transition(VALIDATION → NIC_REVIEW)` unconditionally. Replace with:
   - **HIGH (mean confidence ≥ 0.85):** `VALIDATION → NIC_REVIEW` directly. No human in the loop.
   - **MEDIUM (mean 0.70 ≤ c < 0.85):** `VALIDATION → VALIDATION_REVIEW`. Notify the assigned reviewer (publish to Redis `taxla:updates` channel for UI toast). Reviewer can PATCH an override endpoint to proceed.
   - **LOW (mean < 0.70):** `VALIDATION → HUMAN_REVIEW_REQUIRED`. Operator must re-upload or correct the document.
2. **Add new states to `ApplicationState` enum** — `backend/app/models/state.py`: add `VALIDATION_REVIEW`, `HUMAN_REVIEW_REQUIRED`. Add transitions in `VALID_TRANSITIONS`:
   - `VALIDATION → NIC_REVIEW` (HIGH path)
   - `VALIDATION → VALIDATION_REVIEW` (MEDIUM path)
   - `VALIDATION → HUMAN_REVIEW_REQUIRED` (LOW path)
   - `VALIDATION_REVIEW → NIC_REVIEW` (reviewer approves)
   - `VALIDATION_REVIEW → HUMAN_REVIEW_REQUIRED` (reviewer rejects)
   - `HUMAN_REVIEW_REQUIRED → DOCUMENTS_UPLOADED` (operator re-uploads)
3. **Implement actual validators** — replace the empty `validation_rules` dict in `validation_engine.py`:
   - `PAN`: regex `^[A-Z]{5}\d{4}[A-Z]$` (5 letters, 4 digits, 1 letter — checksums internally valid)
   - `Aadhaar`: 12 digits, optionally space-separated as `XXXX XXXX XXXX`
   - `IFSC`: regex `^[A-Z]{4}0[A-Z0-9]{6}$`
   - `GSTIN`: regex `^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]$`
   - `mobile`: `^[6-9]\d{9}$` (Indian 10-digit, starts 6-9)
   - `email`: `^[\w.+-]+@[\w-]+\.[\w.-]+$`
   - `pincode`: `^\d{6}$`
4. **Per-field validation result** — extend `ExtractedData` with `validation_status` column (already exists; populates now) + `validation_errors` (JSON list). Reuse the existing column if it fits; otherwise add via migration.

---

## Scope (out)

- Do NOT modify the LLM extractor (Phase 02's outputs are the inputs here).
- Do NOT add a UI for the new MEDIUM/LOW paths (Phase 11).
- Do NOT change other API endpoints.

---

## Deliverables checklist

- [ ] `backend/app/models/state.py` — `VALIDATION_REVIEW`, `HUMAN_REVIEW_REQUIRED` added to `ApplicationState` enum.
- [ ] `backend/app/core/state_machine.py` — `VALID_TRANSITIONS` updated with the 5 new edges.
- [ ] `backend/app/services/validation_engine.py` — confidence branching + real regex validators.
- [ ] `backend/app/api/applications.py` or `workflow.py` — new `PATCH /api/v1/applications/{id}/validation-review` endpoint (REVIEWER_AUDITOR only) to override MEDIUM path → `NIC_REVIEW` or → `HUMAN_REVIEW_REQUIRED`.
- [ ] `backend/tests/test_validation.py` — new test file. HIGH/MEDIUM/LOW paths each get a test; each validator regex gets a positive + negative test.
- [ ] Optional Alembic migration if `ExtractedData.validation_errors` column is needed.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`
2. `pytest backend/tests/test_validation.py -v` — all confidence branches + all regex validators pass.
3. `pytest backend/tests/ -q` — full suite green.
4. Manually craft an `ExtractedData` row with mean confidence 0.95, call `validate_application_extractions(app.id)`, assert `app.status == NIC_REVIEW`.
5. Repeat with 0.75 → assert `VALIDATION_REVIEW`.
6. Repeat with 0.50 → assert `HUMAN_REVIEW_REQUIRED`.
7. Verify validators: `validate_pan("ABCDE1234F") == True`, `validate_pan("ABCDE12345") == False`; same for Aadhaar/IFSC/GSTIN/mobile/email/pincode.

---

## Definition of done

- Confidence branching works end-to-end with real OCR output.
- All 7 validators implemented + tested.
- New states and transitions are legal and exercised.
- Reviewer override endpoint exists (RBAC enforced — Phase 05 will gate this).
- All tests pass.

---

## CONTINUATION PROMPT — start Phase 05

```
Starting Phase 05 of the AINCURU × TAXLA remediation. Phase 04 is complete:
- validation_engine.py branches on mean confidence: HIGH→NIC_REVIEW,
  MEDIUM→VALIDATION_REVIEW, LOW→HUMAN_REVIEW_REQUIRED.
- All 7 validators implemented (PAN, Aadhaar, IFSC, GSTIN, mobile, email, pincode) with
  positive + negative tests.
- VALIDATION_REVIEW + HUMAN_REVIEW_REQUIRED states added to ApplicationState enum;
  5 new transitions in VALID_TRANSITIONS.
- New PATCH /api/v1/applications/{id}/validation-review endpoint (RBAC not yet enforced
  — that's this phase).

Read the full plan: documents/implementation phases/phase-05-role-enforcement.md

Goal: Implement require_roles() everywhere. The matrix from
documents/04_user_roles_and_permissions.md:
- SUPER_ADMIN: full access.
- BRANCH_ADMIN: full access within their branch.
- OPERATOR: create apps, upload docs, verify OCR; CANNOT approve NIC; CANNOT do final
  submission.
- REVIEWER_AUDITOR: approve NIC, authorize final submission, override validation;
  CANNOT upload initial docs / do data entry.
- All endpoints that touch Application: assert application.branch_id ==
  current_user.branch_id (or current_user.role == SUPER_ADMIN). Return 403 on mismatch.
- Add require_roles() dependency to: POST /applications, GET /applications,
  GET /applications/{id}, PATCH /applications/{id}, POST /applications/{id}/documents,
  POST /applications/{id}/nic/search, POST /applications/{id}/nic/approve,
  POST /applications/{id}/automation/start, POST /applications/{id}/otp,
  PATCH /applications/{id}/validation-review (new in Phase 04).
- For each, document the allowed roles at the route signature.

After Phase 05 verification, paste the Phase 06 continuation prompt.

---

PHASE 06 CONTINUATION PROMPT:

Starting Phase 06 of the AINCURU × TAXLA remediation. Phase 05 is complete: every
endpoint enforces its role matrix; branch-scope guard helper exists; 403 on mismatch;
matrix documented in each route's docstring.

Read the full plan: documents/implementation phases/phase-06-auth-flow.md

Goal: Replace the hardcoded auto-login with a real auth flow.
Backend:
- POST /api/v1/auth/login (already exists) — keep; ensure it sets refresh token as
  HttpOnly Secure SameSite=Strict cookie per docs/25_authentication.md.
- POST /api/v1/auth/refresh (new) — exchanges refresh cookie for a new access token;
  rotates the refresh cookie.
- POST /api/v1/auth/logout (new) — clears the refresh cookie + (optional) server-side
  blacklist.
Frontend:
- frontend/src/app/login/page.tsx (new) — username/password form.
- frontend/middleware.ts (new) — Next.js middleware that redirects unauthenticated users
  to /login (except for /login itself + /api/v1/auth/* proxied through).
- frontend/src/api/workflow.js — Axios interceptor: 401 → call /auth/refresh → retry once;
  on second 401, redirect to /login.
- frontend/src/stores/authStore.ts (new) — Zustand store for current user info.
```