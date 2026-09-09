# Phase 05 — Role Enforcement + Branch-Scope Guards

**Goal:** Every endpoint enforces the role matrix from `documents/04_user_roles_and_permissions.md`. No cross-branch access. No OPERATOR approving NIC. No REVIEWER_AUDITOR doing data entry.

---

## Pre-requisites

Phases 01-04 complete. Authentication endpoints exist in `backend/app/api/auth.py`.

---

## Scope (in)

1. **`require_roles(*allowed_roles)` dependency** — new function in `backend/app/core/security.py`. Returns the current `User` if their `role` is in `allowed_roles`; otherwise raises 403. Use as `Depends(require_roles(Role.OPERATOR, Role.BRANCH_ADMIN))`.
2. **`assert_branch_scope(user, application)` helper** — same file. If `user.role == SUPER_ADMIN`, allow. Else assert `user.branch_id == application.branch_id`; else 403.
3. **Apply to every application endpoint** — `backend/app/api/applications.py` and any other file under `backend/app/api/`:
   - `POST /api/v1/applications` → OPERATOR, BRANCH_ADMIN, SUPER_ADMIN
   - `GET /api/v1/applications` → OPERATOR, REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN (filtered by branch_id unless SUPER_ADMIN)
   - `GET /api/v1/applications/{id}` → all roles; assert branch scope
   - `PATCH /api/v1/applications/{id}` → OPERATOR, BRANCH_ADMIN, SUPER_ADMIN (and only in `NEW` / `DATA_VERIFICATION` states)
   - `POST /api/v1/applications/{id}/documents` → OPERATOR, BRANCH_ADMIN, SUPER_ADMIN
   - `POST /api/v1/applications/{id}/documents/{did}/extract` → OPERATOR, BRANCH_ADMIN, SUPER_ADMIN
   - `POST /api/v1/applications/{id}/nic/search` → OPERATOR, REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN
   - `POST /api/v1/applications/{id}/nic/approve` → **REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN only** (OPERATOR explicitly forbidden)
   - `POST /api/v1/applications/{id}/automation/start` → OPERATOR, BRANCH_ADMIN, SUPER_ADMIN
   - `POST /api/v1/applications/{id}/otp` → OPERATOR, BRANCH_ADMIN, SUPER_ADMIN (the human-in-the-loop typing the OTP)
   - `PATCH /api/v1/applications/{id}/validation-review` → **REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN only**
   - `POST /api/v1/applications/{id}/submit` → REVIEWER_AUDITOR, BRANCH_ADMIN, SUPER_ADMIN
4. **Document the matrix per route** — each route docstring lists the allowed roles and the branch-scope rule.
5. **Tests** — `backend/tests/test_rbac.py`. New. For each endpoint, one test per allowed role (200), one test per forbidden role (403). Add a cross-branch test: BRANCH_ADMIN_A creates an app, BRANCH_ADMIN_B tries to read → 403.

---

## Scope (out)

- Do NOT change authentication (Phase 06).
- Do NOT add UI for role-aware controls (Phase 11).
- Do NOT change document extraction logic.

---

## Deliverables checklist

- [ ] `backend/app/core/security.py` — `require_roles()` and `assert_branch_scope()` helpers added.
- [ ] Every endpoint in `backend/app/api/applications.py`, `documents.py`, `workflow.py`, `validation.py` (new in Phase 04) uses `Depends(require_roles(...))`.
- [ ] Every endpoint that takes an `application_id` path param calls `assert_branch_scope()` after loading.
- [ ] Each route's docstring lists allowed roles.
- [ ] `backend/tests/test_rbac.py` covers all endpoints × allowed/forbidden roles + cross-branch.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`
2. `pytest backend/tests/test_rbac.py -v` — every test green.
3. `pytest backend/tests/ -q` — full suite still green.
4. Manual: log in as OPERATOR, call `POST /nic/approve` → expect 403 + clear message.
5. Manual: BRANCH_ADMIN_A creates app → BRANCH_ADMIN_B calls GET → expect 403.

---

## Definition of done

- All 13 application-touching endpoints are gated.
- Branch-scope helper prevents cross-branch access.
- Tests cover the matrix and the cross-branch case.
- No regression in existing tests.

---

## CONTINUATION PROMPT — start Phase 06

```
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

After Phase 06 verification, paste the Phase 07 continuation prompt.

---

PHASE 07 CONTINUATION PROMPT:

Starting Phase 07 of the AINCURU × TAXLA remediation. Phase 06 is complete: real login
flow (HttpOnly refresh cookie, /auth/refresh rotation, /auth/logout, Next.js middleware
redirect, Axios 401-refresh-retry interceptor, Zustand authStore). Hardcoded auto-login
deleted.

Read the full plan: documents/implementation phases/phase-07-reviews-certificates.md

Goal: Wire up reviews + certificates per docs/15 (NIC review), docs/16 (final review),
docs/20 (certificate).
- NIC review PATCH: replaces the existing /nic/approve with a proper review record
  (NIC codes selected, justification, reviewer_id, reviewer_role, decided_at) persisted
  in a new `NicReview` table (Application FK, reviewer_id FK, selected_codes JSON,
  justification TEXT, decided_at TIMESTAMP). Application.transitions to NIC_REVIEW
  when no review record yet; to READY_FOR_PORTAL when approved; to NIC_REJECTED_RESOLVE
  when rejected with a resolve path back to NIC_REVIEW.
- Final review PATCH: similar `FinalReview` table (signoff FK, kyc_confirmed BOOL,
  declared_at TIMESTAMP, signoff_method TEXT). Endpoint POST /applications/{id}/final-review.
  Application transitions HUMAN_REVIEW → APPROVED.
- Certificate endpoint: GET /applications/{id}/certificate (returns PDF when
  status==COMPLETED). Fetch from Portal/OCR if not yet cached; otherwise serve from
  Certificate table (already exists; populate it).
- All RBAC stays as Phase 05 set it: NIC review = REVIEWER_AUDITOR+, final review =
  REVIEWER_AUDITOR+, certificate = any role with branch access.
```