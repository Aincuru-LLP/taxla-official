# Phase 01 — Config & Security Hardening

**Goal:** Eliminate the Tier 1 production blockers that exist in the current codebase without changing any business behavior. The app should still boot and behave identically after this phase; you just remove the things that would embarrass you in a security review.

---

## Pre-requisites

None. This is the first phase.

---

## Scope (in)

1. **Move JWT secret to env** — `backend/app/core/config.py:24` has `JWT_SECRET = "taxla_super_secret_jwt_key_change_in_production_2026"` hardcoded. Move to `JWT_SECRET` env var; fail startup if missing in non-dev environments.
2. **Frontend: remove hardcoded operator credentials** — `frontend/src/api/workflow.js:14-32` has `operator@taxla.com` / `Operator@123` baked in. Remove; rely on real login (Phase 06 will add the login page; for now just remove the auto-login and have callers be unauthenticated until Phase 06).
3. **Fix CORS** — `backend/app/main.py:18-24` has `allow_origins=["*"]` + `allow_credentials=True` (browsers reject this combo). Read origins from `CORS_ALLOW_ORIGINS` env var (comma-separated list). Either drop `allow_credentials=True` OR keep it and use explicit origin list — pick based on whether you need cookies (yes for refresh token → keep credentials + explicit origins).
4. **Sanitize exception details** — `backend/app/main.py:35` returns `str(exc)` to clients. Log full traceback server-side; return generic `Internal Server Error` to client with a correlation ID.
5. **FastAPI lifespan instead of `@app.on_event`** — replace `backend/app/main.py:54-57` with `@asynccontextmanager async def lifespan(app)` and `FastAPI(lifespan=lifespan, ...)`.
6. **`datetime.now(UTC)` instead of `datetime.utcnow()`** — `backend/app/core/security.py:13,15` and any other occurrences (`grep -rn "datetime.utcnow" backend/`).
7. **Make DATABASE_URL env-driven honestly** — either commit to SQLite (set SQLite as the documented MVP target, remove `asyncpg` + `psycopg[binary]` from `requirements.txt`, switch `postgresql.UUID` imports in `backend/app/models/domain.py:7` to plain `sqlalchemy.UUID`) OR wire `.env` properly so Pydantic honors the env var. Pick one and document the choice in `README.md`.
8. **Env-driven Next.js proxy** — `frontend/next.config.ts:8` hardcodes `http://127.0.0.1:8000`. Replace with `process.env.BACKEND_URL` (default `http://127.0.0.1:8000`) + create `frontend/.env.example`.
9. **Delete dead `backend/app/schemas/payloads.py`** — 125 lines, zero imports (verified by grep). After deletion, run `grep -rn "from app.schemas.payloads" backend/` to confirm nothing breaks.
10. **Fix `backend/scripts/parse_nic_pdf.py:1-3`** — imports both `fitz` AND `pymupdf` (same library under two names). Pick one, remove the other.

---

## Scope (out)

- No changes to API contracts, schemas, or business logic.
- No new auth flow (Phase 06).
- No frontend routing changes.
- No new dependencies unless absolutely required (e.g. if you commit to SQLite, you can *remove* `asyncpg` and `psycopg[binary]` from `requirements.txt`).

---

## Deliverables checklist

- [ ] `backend/app/core/config.py` — `JWT_SECRET`, `CORS_ALLOW_ORIGINS`, `DATABASE_URL` all sourced from env; fail fast if JWT_SECRET missing in non-dev environments.
- [ ] `backend/app/main.py` — lifespan handler, sanitized exception handler, env-driven CORS.
- [ ] `backend/app/core/security.py` — `datetime.now(datetime.UTC)`.
- [ ] `backend/app/models/domain.py` — `postgresql.UUID` → `sqlalchemy.UUID` IF SQLite path chosen.
- [ ] `backend/requirements.txt` — remove `asyncpg`, `psycopg[binary]` IF SQLite path chosen.
- [ ] `backend/app/schemas/payloads.py` — DELETED.
- [ ] `backend/scripts/parse_nic_pdf.py` — single import.
- [ ] `frontend/src/api/workflow.js` — auto-login removed; `loginOperator` function deleted; remaining calls throw if no token in localStorage.
- [ ] `frontend/next.config.ts` — env-driven backend URL.
- [ ] `frontend/.env.example` — new file with `BACKEND_URL=http://127.0.0.1:8000`.
- [ ] `backend/.env.example` — verify it has `JWT_SECRET=`, `DATABASE_URL=`, `CORS_ALLOW_ORIGINS=`.

---

## Verification steps

1. `cd backend && .venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/macOS).
2. `python -c "from app.core.config import settings; assert settings.JWT_SECRET != 'taxla_super_secret_jwt_key_change_in_production_2026'"` — passes if env override works.
3. `python -c "from app.main import app; print(app.title)"` — app boots.
4. `uvicorn app.main:app --reload` — backend starts, no deprecation warnings about `@app.on_event` or `datetime.utcnow`.
5. `curl -s http://127.0.0.1:8000/health` — returns 200.
6. `cd frontend && npm run dev` — starts on :3000, proxy still works (env default = `http://127.0.0.1:8000`).
7. `npm run build` — Next.js build succeeds.
8. `pytest backend/tests/ -q` — existing tests still pass.
9. `grep -rn "datetime.utcnow" backend/` — returns 0 results.
10. `grep -rn "taxla_super_secret" backend/` — returns 0 results.

---

## Definition of done

- No hardcoded secrets anywhere in source.
- No deprecated FastAPI patterns.
- CORS works for browser requests (test from a non-localhost origin if possible).
- All existing tests pass.
- The `payloads.py` dead file is gone.
- The `parse_nic_pdf.py` script imports a single PDF library.
- The frontend builds and the API proxy still resolves to the backend.

---

## CONTINUATION PROMPT — start Phase 02

```
Starting Phase 02 of the AINCURU × TAXLA remediation. Phase 01 is complete:
- JWT_SECRET sourced from env, fails fast if missing in non-dev.
- CORS reads CORS_ALLOW_ORIGINS env var; allow_credentials aligned with config.
- Sanitized global exception handler with correlation ID + full server-side traceback.
- FastAPI lifespan in place; no @app.on_event warnings.
- datetime.now(datetime.UTC) used everywhere; zero datetime.utcnow() left.
- DATABASE_URL honestly env-driven; chose SQLite as MVP target; postgresql.UUID
  replaced with sqlalchemy.UUID; asyncpg/psycopg removed from requirements.txt
  (OR: wired Postgres properly — confirm which).
- frontend/next.config.ts uses process.env.BACKEND_URL with sensible default.
- frontend/src/api/workflow.js no longer auto-logins; loginOperator deleted.
- backend/app/schemas/payloads.py deleted; parse_nic_pdf.py has single import.
- All existing tests pass; npm run build succeeds; backend boots without warnings.

Read the full plan: documents/implementation phases/phase-02-real-ocr.md

Goal: Replace the hardcoded mock_ocr_text in backend/worker/ocr_worker.py with a real
OCR call. pytesseract is cross-platform (works on Windows AND Linux). PaddleOCR stays
Linux-only per requirements.txt — keep the sys_platform gate, do not import on Windows.
Handle PDF (pdf2image) and image (PIL) inputs. Emit per-field confidence and bounding
boxes (ExtractedData model already has both columns). Decide whether to compute
per-field confidence (Tesseract gives word-level confidences) or per-document.

After Phase 02 verification passes, paste the Phase 03 continuation prompt below
into a new chat.

---

PHASE 03 CONTINUATION PROMPT:

Starting Phase 03 of the AINCURU × TAXLA remediation. Phase 02 is complete: real OCR
is now wired (pytesseract on Windows + PaddleOCR on Linux), handling PDF and image
inputs, emitting per-field confidence and bounding boxes.

Read the full plan: documents/implementation phases/phase-03-workflow-engine.md

Goal: Wire Workflow.current_node + write WorkflowEvent rows on every state transition.
Currently the workflow row is created once but never updated. Add the missing states
to VALID_TRANSITIONS (AADHAAR_OTP, PAN_VERIFICATION, DATA_VERIFICATION, REGISTERED,
DUPLICATE_PAN_DETECTED, UAM_NOT_FOUND). Remove or explicitly document the RESUME
state bypass in app/core/state_machine.py:53. Replace the direct mutation in
worker/playwright_agent.py:99-111 with a proper transition() call.
```