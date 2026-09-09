# Phase 11 — Frontend Spec Compliance

**Goal:** Frontend spec compliance per `docs/06_tech_stack.md`, `docs/29_frontend_architecture.md`, `docs/33_audit_timeline.md`. Big frontend phase.

---

## Pre-requisites

Phases 01, 05, 06 complete. Login + auth + RBAC wired.

---

## Scope (in)

1. **Install + adopt React Query, Zustand, React Hook Form, Zod** — `frontend/package.json`. Replace raw `useState` + `useEffect` + axios data fetching with typed React Query hooks in a new `frontend/src/lib/api-client.ts`. Replace ad-hoc forms with React Hook Form + Zod schemas.
2. **Convert 5 `.jsx` → `.tsx`** with proper prop interfaces:
   - `Sidebar.tsx`
   - `KanbanDashboard.tsx`
   - `ApplicationWorkspace.tsx`
   - `NICReviewPanel.tsx`
   - `OTPInputModal.tsx`
3. **New domain molecules**:
   - `DocumentViewer.tsx` — renders PDF (via `react-pdf`) or image with zoom + rotate.
   - `ExtractedDataForm.tsx` — RHF + Zod form binding to `ExtractedData` fields.
   - `WorkflowStepper.tsx` — visualizes the state machine.
   - `StatusBadge.tsx` — colored pill per `ApplicationState`.
   - `ConfidenceIndicator.tsx` — bar per-field, color-coded HIGH/MEDIUM/LOW.
   - `DataField.tsx` — key/value with confidence badge.
4. **Real audit timeline** — `ApplicationWorkspace.tsx`. Replace the placeholder div with `<AuditTimeline />` that fetches `/api/v1/applications/{id}/audit` and `/api/v1/applications/{id}/workflow-events` (both new endpoints).
5. **Dark/light consolidation** — pick dark-first per spec. Update `applications/[id]/page.tsx` + `settings/page.tsx` to use the dark theme tokens.
6. **New routes** — `frontend/src/app/automations/page.tsx`, `workflows/page.tsx`, `ai-agents/page.tsx` — at least functional placeholder pages.
7. **Shared `useWebSocket` hook** — `frontend/src/hooks/useWebSocket.ts`. Auth'd (passes access token as query param), debounced (no per-byte refetch storm), per-message-type routing. Used by `KanbanDashboard` + `ApplicationWorkspace`.
8. **Settings tabs** — `frontend/src/app/settings/page.tsx`. All 5 tabs implement save handlers.
9. **Accessibility pass** — labels for every input; `aria-label` for icon buttons; keyboard nav tested.

---

## Scope (out)

- Do NOT rebuild the entire design system. Extend the existing `components/ui/*`.
- Do NOT change the backend.

---

## Deliverables checklist

- [ ] `frontend/package.json` — `@tanstack/react-query`, `zustand`, `react-hook-form`, `zod`, `react-pdf` added.
- [ ] `frontend/src/lib/api-client.ts` — typed React Query hooks + Zod schemas.
- [ ] `frontend/src/hooks/useWebSocket.ts` — auth'd, debounced, typed.
- [ ] 5 `.jsx` → `.tsx` conversions.
- [ ] 6 new domain molecules (`DocumentViewer`, `ExtractedDataForm`, `WorkflowStepper`, `StatusBadge`, `ConfidenceIndicator`, `DataField`).
- [ ] 3 new routes (`/automations`, `/workflows`, `/ai-agents`).
- [ ] Audit timeline real (new endpoints in `backend/app/api/applications.py` + `workflow.py`).
- [ ] Dark theme consistent across all pages.
- [ ] Settings tabs functional.
- [ ] Accessibility pass.

---

## Verification steps

1. `cd frontend && npm install`
2. `npm run build` — no TS errors.
3. `npm run dev` — app boots; visit every route; no console errors.
4. `npx tsc --noEmit` — clean.
5. Open Chrome DevTools → Lighthouse → Accessibility → score ≥ 90.
6. Verify KanbanDashboard updates on WebSocket event WITHOUT a refetch storm (no rapid network log).
7. Verify login flow → applications → workspace → upload → extract → validate → NIC review → automation start works end-to-end.

---

## Definition of done

- Frontend matches the spec's tech stack.
- All `.jsx` are `.tsx`.
- All spec-mandated components exist.
- Dark theme consistent.
- Accessibility acceptable.
- No regressions in the user flow.

---

## CONTINUATION PROMPT — start Phase 12

```
Starting Phase 12 of the AINCURU × TAXLA remediation. Phase 11 is complete: React Query,
Zustand, RHF, Zod adopted; 5 .jsx → .tsx; DocumentViewer/ExtractedDataForm/
WorkflowStepper/StatusBadge/ConfidenceIndicator/DataField exist; audit timeline real;
dark/light consolidated; /automations + /workflows + /ai-agents routes exist; 404 +
breadcrumbs + user menu; useWebSocket debounced + auth'd; settings tabs functional;
accessibility pass done.

Read the full plan: documents/implementation phases/phase-12-webhooks.md

Goal: External webhooks per docs/24_webhooks.md.
- Backend: webhooks table (id, branch_id, name, url, secret, subscribed_events JSON,
  is_active, created_at, updated_at, last_triggered_at, last_status, last_error);
  HMAC-SHA256 signing of outgoing payloads; per-webhook retry with exponential
  backoff (1m, 5m, 30m, 2h); webhook delivery log (webhook_deliveries table: id,
  webhook_id FK, event_id, attempt_number, status_code, response_body, attempted_at).
- On every state transition (after Phase 08 publishes to Redis taxla:events), the
  dispatcher (Phase 08) ALSO looks up active webhooks for the branch and posts the
  payload to each. Headers: X-Taxla-Event, X-Taxla-Delivery, X-Taxla-Signature
  (HMAC of body using secret), X-Taxla-Timestamp.
- API: POST /api/v1/webhooks, GET /api/v1/webhooks, PATCH /api/v1/webhooks/{id},
  DELETE /api/v1/webhooks/{id}, GET /api/v1/webhooks/{id}/deliveries (paginated).
  RBAC: BRANCH_ADMIN+ for write.
- Frontend: /integrations page (new) — list, create, toggle, view delivery log.
- Tests: backend/tests/test_webhooks.py — outbound delivery succeeds; HMAC verifies;
  retry kicks in on 500; max attempts = 4.
```