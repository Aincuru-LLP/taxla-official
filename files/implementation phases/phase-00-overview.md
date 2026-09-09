# Phase 00 — Overview & Execution Order

**Project:** AINCURU × TAXLA — MSME/Udyam registration automation platform
**Source spec:** [documents/aincuru_×_taxla_—_00_master_plan.md](documents/aincuru_×_taxla_—_00_master_plan.md) … [documents/aincuru_×_taxla_—_39_build_rules.md](documents/aincuru_×_taxla_—_39_build_rules.md) + [documents/input requirmentsv2.md](documents/input requirmentsv2.md)
**Gap analysis (authoritative):** [C:\Users\asus\.claude\plans\backend-frontend-documents-understand-snug-zephyr.md](C:\Users\asus\.claude\plans\backend-frontend-documents-understand-snug-zephyr.md)

---

## Why these phases

The approved gap analysis lists ~35 issues across 4 priority tiers. To keep each phase small enough to fit in one chat (your context budget), I split Tier 1 + Tier 2 into **12 working phases** plus this overview. Tier 3 (frontend polish) and Tier 4 (hardening) are absorbed into the relevant working phases instead of being standalone.

Each phase is:
- **Self-contained** — has clear pre-reqs, scope, deliverables, verification, and a continuation prompt.
- **Context-bounded** — sized for a single fresh chat (~5–15 files modified).
- **Reversible** — every change keeps the app runnable at the end (no half-broken intermediate states).

---

## Execution order

| # | Phase | Depends on | Tier | Chat effort | Status |
|---|---|---|---|---|---|
| 01 | [Config & Security Hardening](documents/implementation phases/phase-01-config-security.md) | — | Tier 1 | Small | ✅ Written |
| 02 | [Real OCR Pipeline](documents/implementation phases/phase-02-real-ocr.md) | 01 | Tier 2 | Medium | ✅ Written |
| 03 | [Workflow Engine — Make It Real](documents/implementation phases/phase-03-workflow-engine.md) | 01 | Tier 2 | Medium | ✅ Written |
| 04 | [Validation Engine — Confidence Branching](documents/implementation phases/phase-04-validation-engine.md) | 02 | Tier 2 | Small | ✅ Written |
| 05 | [Role Enforcement](documents/implementation phases/phase-05-role-enforcement.md) | 01 | Tier 1 | Medium | ✅ Written |
| 06 | [Auth Flow Completion](documents/implementation phases/phase-06-auth-flow.md) | 01, 05 | Tier 1 | Medium | ✅ Written |
| 07 | [Reviews + Certificates](documents/implementation phases/phase-07-reviews-certificates.md) | 05, 06 | Tier 2 | Medium | ✅ Written |
| 08 | [Trigger-Action System](documents/implementation phases/phase-08-trigger-action.md) | 03 | Tier 2 | Medium-Large | ✅ Written |
| 09 | [Real Udyam Portal Automation](documents/implementation phases/phase-09-udyam-portal.md) | 01, 03, 06 | Tier 2 | Large | ✅ Written |
| 10 | [NIC Dataset Expansion](documents/implementation phases/phase-10-nic-expansion.md) | — | Tier 4 | Medium | ✅ Written |
| 11 | [Frontend Spec Compliance](documents/implementation phases/phase-11-frontend-spec.md) | 05, 06, 07 | Tier 3 | Large | ✅ Written |
| 12 | [External Webhooks](documents/implementation phases/phase-12-webhooks.md) | 01 | Tier 2 | Small | ✅ Written |

Phase 01 is mandatory first. After that, 02 + 03 + 05 + 10 can be done in any order (parallel branches). The full dependency graph is below.

---

## Dependency graph

```
                   ┌── 02 ── 04
                   │
01 ────────────────┼── 03 ── 08 ───── 09
                   │            ╲   ╱
                   ├── 05 ── 06 ──┴───── 07 ── 11
                   │   ╲           ╲        ╱
                   │    ╲           ╲      ╱
                   │     ╲           ╲    ╱
                   └──────╲─────────── 11
                          │
                          └── (10 standalone — no deps)

12 ─── depends only on 01
```

Reading: Phase 01 is the root. From there, **02, 03, 05, 10** can run in any order. Once those land, **06** unlocks, then **04, 07, 08** in parallel. Phase **09** needs 03 + 06 done. Phase **11** is the frontend rollup — wait until 05, 06, 07 are done. Phase **12** can run any time after 01 (it only needs RBAC and the dispatcher).

---

## File index

| File | Lines | Topic |
|---|---:|---|
| [phase-00-overview.md](documents/implementation phases/phase-00-overview.md) | 103 | This file |
| [phase-01-config-security.md](documents/implementation phases/phase-01-config-security.md) | 124 | Secrets, CORS, lifespan, UTC, env-driven config |
| [phase-02-real-ocr.md](documents/implementation phases/phase-02-real-ocr.md) | 115 | pytesseract + pdf2image + per-field confidence |
| [phase-03-workflow-engine.md](documents/implementation phases/phase-03-workflow-engine.md) | 114 | transition() writes WorkflowEvent; missing states |
| [phase-04-validation-engine.md](documents/implementation phases/phase-04-validation-engine.md) | 137 | Confidence branching + 7 regex validators |
| [phase-05-role-enforcement.md](documents/implementation phases/phase-05-role-enforcement.md) | 125 | require_roles() + branch-scope guards |
| [phase-06-auth-flow.md](documents/implementation phases/phase-06-auth-flow.md) | 134 | Login + refresh + middleware + authStore |
| [phase-07-reviews-certificates.md](documents/implementation phases/phase-07-reviews-certificates.md) | 138 | NicReview + FinalReview + certificate PDF |
| [phase-08-trigger-action.md](documents/implementation phases/phase-08-trigger-action.md) | 157 | Redis pub/sub + 5 action types + seeds |
| [phase-09-udyam-portal.md](documents/implementation phases/phase-09-udyam-portal.md) | 142 | Aadhaar/OTP/PAN/form/submit/certificate |
| [phase-10-nic-expansion.md](documents/implementation phases/phase-10-nic-expansion.md) | 135 | Full ~1,300 NIC codes + FAISS |
| [phase-11-frontend-spec.md](documents/implementation phases/phase-11-frontend-spec.md) | 110 | React Query/Zustand/RHF/Zod + .tsx + 6 molecules |
| [phase-12-webhooks.md](documents/implementation phases/phase-12-webhooks.md) | 128 | HMAC-signed + retry-with-backoff |

**Total:** 13 files, ~1,660 lines of phase instructions.

---

## Per-phase file format

Every phase file follows this structure:

1. **Title & one-line goal**
2. **Pre-requisites** — which earlier phases must be done
3. **Scope (in)** — explicit deliverables, file:line targets
4. **Scope (out)** — what to NOT touch in this phase
5. **Deliverables checklist** — exact files to modify/create
6. **Verification steps** — concrete commands to run end-to-end
7. **Definition of done** — what "this phase is finished" looks like
8. **CONTINUATION PROMPT** — verbatim block to paste into a new chat to start the next phase

---

## How to execute

1. Open a fresh chat.
2. Paste the **CONTINUATION PROMPT** of the previous phase (or, for the very first chat, say *"Starting Phase 01 — Config & Security Hardening. Open `documents/implementation phases/phase-01-config-security.md` and execute it."*).
3. Run through the phase's deliverables.
4. After the phase's verification passes, copy the next phase's **CONTINUATION PROMPT** and start a fresh chat with it.

If you want to parallelize (after Phase 01 lands), spin up 2–3 chats simultaneously — one per branch of the dependency graph. Each chat owns its phase end-to-end.

---

## Common gotchas (read once before starting)

1. **SQLite vs Postgres decision.** Phase 01 forces the call. Default: **commit to SQLite for MVP**, remove `asyncpg`/`psycopg[binary]` from `requirements.txt`, switch `postgresql.UUID` imports to plain `sqlalchemy.UUID`. If you keep Postgres for dev, wire `.env` properly via `pydantic-settings`.
2. **Tesseract binary.** Phase 02 requires the Tesseract binary, which is not pip-installable. `apt install tesseract-ocr` on Linux, `brew install tesseract` on macOS, or download from UB-Mannheim for Windows. The README must call this out.
3. **Redis required.** Phases 06, 08, 09, 12 all rely on Redis pub/sub. Without Redis running, none of them work. Start it before any chat that touches triggers or webhooks.
4. **Branch scope vs SUPER_ADMIN.** Every RBAC check must allow `SUPER_ADMIN` to bypass branch scoping (operators in admin role often need cross-branch access for support). Phase 05 establishes this pattern; subsequent phases reuse it.
5. **Triggers + webhooks share a Redis channel.** Phase 08 publishes `taxla:events`; Phase 12's webhook dispatcher subscribes to the same channel. Make sure you don't create a second publisher.
6. **`.env` first commit.** Never commit `.env`. Phase 01 only writes `.env.example`. Confirm `.env` is in `.gitignore` before Phase 02 starts.
7. **State machine is the spine.** Phases 03, 04, 07, 09, 12 all extend the state machine. Run `pytest backend/tests/test_state_machine.py -v` after each one. Don't skip.
8. **Frontend build is slow.** Phase 11 will touch every page. Plan for ~30 min of `npm install` + `npm run build` time. Have the dev server hot-reloading while you edit.
9. **Playwright + Windows.** Phase 09's worker uses Playwright Chromium. On Windows, `playwright install chromium` may need to run with admin or in a specific shell. The phase file calls this out.
10. **The v2 placeholder files** (see below) — leave alone until Phase 11 is done.

---

## Risk callouts

| Phase | Risk | Mitigation |
|---|---|---|
| 01 | Breaking import paths when removing `asyncpg` | Run `pytest backend/tests/ -q` after every removal |
| 02 | OCR accuracy on real Indian documents < 90% | Acceptable — Phase 04's confidence branching handles low-confidence cases |
| 03 | Existing tests assert old state names | Grep for `RESUME`, `EXCEPTION`, etc. before refactoring |
| 04 | MEDIUM path inflates reviewer workload | Phase 08 trigger can auto-approve HIGH; reviewer only sees MEDIUM |
| 06 | Refresh-token rotation race condition | Use Redis `SET NX` with TTL when issuing; rotate on every use |
| 08 | Trigger spam (every transition fires many) | Pattern matching + condition_json filter on dispatcher |
| 09 | Real `udyamregistration.gov.in` selectors change | Selector registry in `portal_selectors.py` lets you swap LIVE/MOCK; fixture tests run in MOCK |
| 11 | 5 `.jsx → .tsx` conversion breaks hot-reload | Do one at a time, keep dev server running |
| 12 | HMAC secret leaked in logs | Mask `secret` field in any `__repr__` or log statement |

---

## Notes on the v2 placeholder files

`documents/master prompt updated v2` and `documents/pagesnavigationsv2.md` are 0 bytes. If you want them populated with a synthesized v2 master prompt + page-by-page navigation map, do that AFTER Phase 11 (so the frontend spec is settled first) — otherwise the v2 docs will go stale immediately.

---

## CONTINUATION PROMPT — start Phase 01

```
Starting Phase 01 of the AINCURU × TAXLA remediation.

Read the full plan: documents/implementation phases/phase-01-config-security.md
(also cross-reference C:\Users\asus\.claude\plans\backend-frontend-documents-understand-snug-zephyr.md
for the gap matrix.)

Goal: Tier 1 production blockers — move secrets to env, fix CORS, sanitize exception
details, replace deprecated @app.on_event with FastAPI lifespan, switch datetime.utcnow()
to datetime.now(UTC), make DATABASE_URL env-driven, replace hardcoded frontend credentials
and localhost proxy with env vars, delete the unused app/schemas/payloads.py file, fix
the duplicate fitz/pymupdf import in scripts/parse_nic_pdf.py.

After completing Phase 01, paste the Phase 02 continuation prompt below into a new chat:

---

PHASE 02 CONTINUATION PROMPT:

Starting Phase 02 of the AINCURU × TAXLA remediation. Phase 01 is complete: JWT secret
moved to env, CORS fixed, exception details sanitized, FastAPI lifespan in use, datetime.UTC
in use, DATABASE_URL env-driven, hardcoded frontend credentials removed, localhost proxy
env-driven, dead app/schemas/payloads.py deleted, scripts/parse_nic_pdf.py duplicate
import fixed.

Read the full plan: documents/implementation phases/phase-02-real-ocr.md

Goal: Replace the hardcoded mock_ocr_text in backend/worker/ocr_worker.py with a real
OCR call using pytesseract (cross-platform; PaddleOCR stays Linux-only per requirements.txt).
Handle PDF inputs via pdf2image and image inputs via PIL. Emit per-field confidence scores
and bounding boxes (already in the ExtractedData model).
```