# Phase 12 — External Webhooks

**Goal:** Allow branches to register webhook URLs that receive every state transition. HMAC-signed payloads with retry. Per docs/24_webhooks.md.

---

## Pre-requisites

Phases 01, 03, 05, 08 complete. State machine publishes events. RBAC enforced.

---

## Scope (in)

1. **New table `webhooks`** — Alembic migration. Columns:
   - `id UUID PK`
   - `branch_id UUID FK→branches`
   - `name TEXT`
   - `url TEXT`
   - `secret TEXT` (HMAC key; generated server-side; only returned once at create time)
   - `subscribed_events JSONB` (array of event names; empty = all events)
   - `is_active BOOL DEFAULT true`
   - `created_at`, `updated_at`, `last_triggered_at`, `last_status INT`, `last_error TEXT`
2. **New table `webhook_deliveries`** — `(id UUID PK, webhook_id UUID FK→webhooks ON DELETE CASCADE, event_id UUID, attempt_number INT, status_code INT, response_body TEXT, attempted_at TIMESTAMP, error TEXT)`.
3. **Dispatcher hook** — `backend/app/services/triggers.py` (Phase 08's dispatcher). After publishing to Redis, also look up active webhooks for the branch (filtered by `subscribed_events` if non-empty) and enqueue a delivery.
4. **Outbound delivery** — `backend/app/services/webhook_delivery.py`:
   - `httpx.AsyncClient.post(url, json=payload, headers={...})` with 10s timeout.
   - Headers: `X-Taxla-Event`, `X-Taxla-Delivery` (UUID), `X-Taxla-Signature: sha256=<HMAC of body using webhook.secret>`, `X-Taxla-Timestamp` (unix seconds).
   - 2xx → success, log to `webhook_deliveries`.
   - non-2xx or timeout → failure, log + retry with exponential backoff: 1m, 5m, 30m, 2h. Max 4 attempts. After 4th failure, mark webhook `last_error`, optionally `is_active=false` (configurable).
5. **API** — `backend/app/api/webhooks.py`:
   - `POST /api/v1/webhooks` — create. Returns the secret once.
   - `GET /api/v1/webhooks` — list (paginated, branch-scoped).
   - `PATCH /api/v1/webhooks/{id}` — toggle / edit. RBAC: BRANCH_ADMIN+.
   - `DELETE /api/v1/webhooks/{id}` — soft delete (set `is_active=false`). RBAC: BRANCH_ADMIN+.
   - `GET /api/v1/webhooks/{id}/deliveries` — paginated delivery log. RBAC: any role with branch scope.
6. **Frontend** — `frontend/src/app/integrations/page.tsx`. List + create modal + secret-once display + per-webhook toggle + delivery log drilldown.
7. **Tests** — `backend/tests/test_webhooks.py`:
   - Create webhook + trigger an event → outbound POST observed at the target URL.
   - Verify HMAC signature is correct (compute locally, compare).
   - Mock a 500 response from the target → first retry is scheduled at 1m (use `freezegun` to advance time).
   - After 4 failures, `is_active` stays true but `last_error` is set; the trigger_action dispatcher skips it for the rest of the test (we don't auto-disable by default).
   - HMAC test: tampering the body invalidates the signature.

---

## Scope (out)

- Do NOT support webhook-level filtering by application (branch scope only).
- Do NOT add a visual delivery-replay UI (use the log table; replay is a future feature).

---

## Deliverables checklist

- [ ] `backend/app/models/domain.py` — `Webhook`, `WebhookDelivery` models.
- [ ] `backend/alembic/versions/<hash>_webhooks.py` — migration.
- [ ] `backend/app/services/triggers.py` — dispatcher enqueues webhook deliveries.
- [ ] `backend/app/services/webhook_delivery.py` — outbound POST + HMAC + retry.
- [ ] `backend/app/api/webhooks.py` — CRUD + deliveries endpoint.
- [ ] `backend/app/main.py` — router included.
- [ ] `backend/tests/test_webhooks.py` — full coverage.
- [ ] `frontend/src/app/integrations/page.tsx` — list + create + deliveries.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`
2. `alembic upgrade head`
3. `pytest backend/tests/test_webhooks.py -v` — green.
4. `pytest backend/tests/ -q` — full suite green.
5. Start backend + worker. Use `https://webhook.site/<uuid>` as a test target. Create a webhook pointing to that URL. Trigger an event. Confirm webhook.site receives the payload + valid HMAC.
6. Frontend: create a webhook, see it listed, view its delivery log, toggle it off.

---

## Definition of done

- Webhooks persist + receive signed payloads.
- HMAC verified.
- Retries work with exponential backoff.
- Delivery log captures every attempt.
- `/integrations` page functional.
- All tests pass.

---

## FINAL CONTINUATION PROMPT — All 12 phases complete

```
All 12 phases of the AINCURU × TAXLA remediation are complete:

Tier 1 — Production blockers:
- Phase 01: Config & Security Hardening — secrets in env, CORS fixed, lifespan, UTC
  timestamps, DATABASE_URL env-driven, hardcoded creds removed, dead code deleted.
- Phase 05: Role Enforcement + Branch-Scope Guards.
- Phase 06: Real Auth Flow — HttpOnly refresh cookie, /auth/refresh, /auth/logout,
  Next.js middleware, Axios interceptor, Zustand authStore.

Tier 2 — Spec compliance:
- Phase 02: Real OCR Pipeline — pytesseract + pdf2image + PIL + per-field confidence.
- Phase 03: Workflow Engine — transition() writes WorkflowEvent rows atomically;
  RESUME bypass replaced with explicit resume_target; missing states mapped.
- Phase 04: Validation Engine — confidence branching (HIGH/MEDIUM/LOW) + 7 regex
  validators; VALIDATION_REVIEW + HUMAN_REVIEW_REQUIRED states added.
- Phase 07: Reviews + Certificates — NicReview + FinalReview tables, certificate PDF.
- Phase 08: Trigger-Action System — every transition publishes to Redis; dispatcher
  + 5 action types; 3 seed triggers.
- Phase 09: Real Udyam Portal Automation — Aadhaar → OTP → PAN → form → submit →
  certificate download; full error matrix.
- Phase 10: NIC Dataset Expansion — full ~1,300 codes + FAISS vector tier.
- Phase 12: External Webhooks — HMAC-signed, retry with backoff.

Tier 3 — Frontend:
- Phase 11: Frontend Spec Compliance — React Query, Zustand, RHF, Zod; .jsx → .tsx;
  6 domain molecules; 3 new routes; dark theme; accessibility.

The project should now match the spec end-to-end. Suggested next steps (NOT in scope
for this 12-phase plan):
- Add the v2 master prompt + pagesnavigationsv2.md content (currently empty) by
  ingesting the now-settled v1 docs.
- Set up CI/CD (GitHub Actions or equivalent) that runs pytest + npm run build on every
  PR.
- Add observability (Sentry for errors, OpenTelemetry for traces, Prometheus for
  metrics).
- Migrate from SQLite to PostgreSQL when moving off MVP.
- Run a real load test against the Playwright worker (Phase 09) to tune the queue.
```