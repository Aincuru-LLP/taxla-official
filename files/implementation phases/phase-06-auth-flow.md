# Phase 06 — Real Auth Flow (Login + Refresh + Middleware)

**Goal:** Replace the hardcoded `operator@taxla.com` / `Operator@123` auto-login in `frontend/src/api/workflow.js` with a real authentication flow. HttpOnly refresh cookie, Axios 401-refresh-retry, Next.js middleware redirect, Zustand auth store.

---

## Pre-requisites

Phases 01 + 05 complete. Login endpoint exists; `require_roles()` works.

---

## Scope (in)

### Backend

1. **`POST /api/v1/auth/login`** — already exists. Modify so it sets a refresh token as an `HttpOnly; Secure; SameSite=Strict; Path=/` cookie. Access token (short-lived, ~15 min) stays in the JSON response body.
2. **`POST /api/v1/auth/refresh`** (new) — reads the refresh cookie, validates it, rotates it (issues new one, marks old revoked in Redis with TTL = refresh token expiry), returns a new access token.
3. **`POST /api/v1/auth/logout`** (new) — revokes the refresh cookie (Redis blacklist), clears the cookie with `Set-Cookie: refresh_token=; Max-Age=0`.
4. **`GET /api/v1/auth/me`** — already exists. Returns the current user (used by the Zustand store to bootstrap).
5. **Token signing** — keep HS256 + `python-jose` (per Phase 01). Refresh tokens are signed JWTs with `typ: refresh`.

### Frontend

6. **`frontend/src/app/login/page.tsx`** — new. Username/password form; on submit `POST /api/v1/auth/login`; on success redirect to `/applications`; on failure show inline error. Loading state. No "remember me" — cookies handle persistence.
7. **`frontend/middleware.ts`** — new. Next.js middleware on every non-API, non-static path. If no access token cookie is present (the frontend mirrors the access token in memory only; middleware checks a separate short-lived presence cookie), redirect to `/login?from=<path>`. Skip for `/login` itself and `/api/v1/auth/*` (proxied through to backend).
8. **`frontend/src/api/workflow.js`** — Axios interceptor:
   - On 401: call `POST /api/v1/auth/refresh` once.
   - If refresh succeeds: retry original request, return.
   - If refresh fails: clear in-memory token + redirect to `/login`.
9. **`frontend/src/stores/authStore.ts`** — new. Zustand store: `{ user: User | null, accessToken: string | null, setAuth, clearAuth }`. Persist nothing — session dies on tab close, user re-logs in via refresh or login page.
10. **`frontend/src/components/Sidebar.tsx`** — Add a "Logout" button that calls `/auth/logout` + `clearAuth()` + `router.push('/login')`.
11. **Remove hardcoded credentials** — already done in Phase 01; verify nothing reintroduced.

---

## Scope (out)

- Do NOT add 2FA / MFA.
- Do NOT add SSO.
- Do NOT add "forgot password" — out of MVP.

---

## Deliverables checklist

- [ ] `backend/app/api/auth.py` — login sets HttpOnly refresh cookie; new refresh + logout endpoints; Redis blacklist for revoked refresh tokens.
- [ ] `frontend/src/app/login/page.tsx` — new login page.
- [ ] `frontend/middleware.ts` — redirect unauthenticated users.
- [ ] `frontend/src/api/workflow.js` — Axios 401-refresh-retry interceptor.
- [ ] `frontend/src/stores/authStore.ts` — Zustand auth store.
- [ ] `frontend/src/components/Sidebar.tsx` — Logout button.
- [ ] No hardcoded credentials anywhere in frontend source.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`; start uvicorn.
2. `cd frontend && npm run dev`; start Next.js.
3. Visit `/applications` while logged out → redirected to `/login?from=/applications`.
4. Log in as `operator@taxla.com` / `Operator@123` → redirected to `/applications`.
5. Open DevTools → Application → Cookies → confirm `refresh_token` is HttpOnly + Secure (or SameSite=Strict in dev).
6. Wait until access token expires (15 min, or temporarily lower for testing) → confirm Axios interceptor refreshes silently — no UI flicker.
7. Click Logout → redirected to `/login`; refresh cookie cleared.
8. Re-attempt to load `/applications` → redirected to `/login`.
9. `grep -rn "operator@taxla" frontend/src/` returns 0 results.
10. `pytest backend/tests/ -q` — full suite green.

---

## Definition of done

- No hardcoded credentials anywhere.
- Login page works.
- Refresh cookie is HttpOnly + Secure + SameSite=Strict.
- Axios interceptor refreshes on 401 without UI flicker.
- Middleware redirects unauthenticated users.
- Logout clears state.
- All tests pass.

---

## CONTINUATION PROMPT — start Phase 07

```
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

After Phase 07 verification, paste the Phase 08 continuation prompt.

---

PHASE 08 CONTINUATION PROMPT:

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
```