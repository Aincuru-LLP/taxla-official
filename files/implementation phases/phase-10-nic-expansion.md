# Phase 10 — NIC Dataset Expansion

**Goal:** Expand the NIC dataset from ~94 hand-curated codes to the full ~1,300 codes from the official NIC 2008 handbook. Improve keyword + vector matching so the LLM rerank has better input.

---

## Pre-requisites

Phases 01 (duplicate fitz import fix) + 02 complete. NIC service uses 3-tier matching.

---

## Scope (in)

1. **Fix `backend/scripts/parse_nic_pdf.py`** — already done in Phase 01 (single import). Confirm it works.
2. **Re-parse the full handbook** — run the script against the official NIC-2008 PDF (download if not already at `data/NIC-2008.pdf`). Expected output: ~1,300 codes spanning sections A through U.
3. **Re-run `scripts/generate_nic_data.py`** — regenerate `data/nic_2008.json` with the full set.
4. **Validate the dataset** — every entry must match `^[0-9]{2,5}$`, every entry must have a non-empty description, no duplicate codes. Add a `scripts/validate_nic_dataset.py` that asserts these and exits non-zero on failure.
5. **Vector tier** — `backend/app/services/nic_service.py`. Rebuild embeddings:
   - Embed each NIC code's description text using `sentence-transformers` (`all-MiniLM-L6-v2`) or Ollama's `nomic-embed-text`. Pick whichever is already in `requirements.txt` / available.
   - Store in `data/nic_2008.faiss` (FAISS index). Keyed by NIC code.
   - At query time, embed the user's activity description, search top-K (default K=10), pass to the LLM rerank tier.
6. **Keyword tier** — expand the keyword → code map. Use the class-level + group-level descriptions from the full dataset to seed keywords. If `manufacturing paper` is in a class description, `paper` becomes a keyword for every code in that class.
7. **Tests** — `backend/tests/test_nic_classification.py`:
   - Assert at least 1,000 distinct codes loadable from `data/nic_2008.json`.
   - Assert the FAISS index is built (or builds on first call) and returns results.
   - Smoke test: `suggest_nic("manufacturing paper")` returns the right NIC code in top-3.
   - Smoke test: `suggest_nic("software development services")` finds IT-related codes in top-3.

---

## Scope (out)

- Do NOT change the LLM rerank logic (Phase 02 is fine; it's the input that improves here).
- Do NOT change the API surface.

---

## Deliverables checklist

- [ ] `backend/scripts/parse_nic_pdf.py` — confirmed working; parses full handbook.
- [ ] `backend/scripts/generate_nic_data.py` — regenerates `data/nic_2008.json`.
- [ ] `data/nic_2008.json` — ~1,300 codes with descriptions.
- [ ] `data/nic_2008.faiss` — vector index built.
- [ ] `scripts/validate_nic_dataset.py` — validator script.
- [ ] `backend/app/services/nic_service.py` — vector tier uses FAISS; keyword tier expanded.
- [ ] `backend/tests/test_nic_classification.py` — coverage tests pass; smoke tests green.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`
2. `python scripts/parse_nic_pdf.py data/NIC-2008.pdf` — runs to completion.
3. `python scripts/generate_nic_data.py` — regenerates JSON.
4. `python scripts/validate_nic_dataset.py` — exits 0.
5. `pytest backend/tests/test_nic_classification.py -v` — green.
6. `pytest backend/tests/ -q` — full suite green.
7. Manual: `python -c "from app.services.nic_service import suggest_nic; print(suggest_nic('manufacturing paper')[:3])"` → returns paper / pulp-related codes in top-3.

---

## Definition of done

- ~1,300 NIC codes loadable.
- Vector index builds and queries.
- Keyword + vector + LLM rerank pipeline produces top-3 hits ≥90% on the smoke set.
- All tests pass.

---

## CONTINUATION PROMPT — start Phase 11

```
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

---

PHASE 12 CONTINUATION PROMPT:

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