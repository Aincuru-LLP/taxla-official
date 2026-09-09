# Phase 03 — Workflow Engine — Make It Real

**Goal:** The `workflows` and `workflow_events` tables exist but nothing ever writes to them after the initial creation. End state: every `transition()` call updates `Workflow.current_node` + writes a `WorkflowEvent` row, and the missing states from `input requirmentsv2.md §39` are wired into `VALID_TRANSITIONS`.

---

## Pre-requisites

Phase 01 complete.

---

## Scope (in)

1. **Make `transition()` write to the workflow engine** — `backend/app/core/state_machine.py`. Currently it only updates `Application.status` and writes an `AuditLog`. Extend it so every call ALSO:
   - Updates `Workflow.current_node` for the application's workflow.
   - Updates `Workflow.status` (RUNNING / COMPLETED / EXCEPTION).
   - Inserts a `WorkflowEvent` row with `node_key`, `event_type` (ENTERED / COMPLETED / FAILED), `status`, `payload_json` (snapshot of the transition's input/output), `error_code` (if FAILED).
2. **Add missing states to `VALID_TRANSITIONS`** — `app/models/state.py` defines them but `VALID_TRANSITIONS` doesn't include: `AADHAAR_OTP`, `PAN_VERIFICATION`, `DATA_VERIFICATION`, `REGISTERED`, `DUPLICATE_PAN_DETECTED`, `UAM_NOT_FOUND`. Map them per the state machine diagram in `input requirmentsv2.md §39`.
3. **Replace the RESUME bypass** — `app/core/state_machine.py:53` currently allows `RESUME → anything`. Replace with: `EXCEPTION` carries an explicit `resume_target` (stored in `Workflow.context_json["resume_target"]`), and the only legal transition from `EXCEPTION` is `EXCEPTION → resume_target`. Recovery is auditable.
4. **Fix the Playwright worker's silent direct mutation** — `worker/playwright_agent.py:99-111` directly assigns `app.status` and writes an `AuditLog`, bypassing `transition()`. Replace with a call to `transition(...)`. Remove the `try/except: pass` — log the error at minimum.
5. **Atomicity** — per `documents/10_workflow_engine.md:44-45`, the transition (Application row update + Workflow row update + WorkflowEvent insert + AuditLog insert) must be a single DB transaction. If any insert fails, roll back the whole transition.

---

## Scope (out)

- No changes to the state names themselves (already defined).
- No changes to API contracts.
- No frontend changes.

---

## Deliverables checklist

- [ ] `backend/app/core/state_machine.py` — extended `transition()` writes all 4 rows atomically; RESUME bypass removed in favor of explicit `resume_target`; missing states mapped.
- [ ] `backend/app/models/state.py` — add `VALIDATION_REVIEW`, `HUMAN_REVIEW_REQUIRED` if Phase 04 needs them (you can also do this in Phase 04).
- [ ] `backend/worker/playwright_agent.py:99-111` — replaced with `transition()` call; no silent pass.
- [ ] `backend/tests/test_state_machine.py` — extended to assert `WorkflowEvent` rows are written; assert `Workflow.current_node` updates; assert atomicity (failure mid-transition rolls back).
- [ ] New `backend/app/repositories/workflow.py` — encapsulates workflow row + event writes (the only repository missing per the gap analysis).

---

## Verification steps

1. `cd backend && .venv\Scripts\activate`
2. `pytest backend/tests/test_state_machine.py -v` — passes including new event-writing assertions.
3. `python -c "from app.core.state_machine import transition, VALID_TRANSITIONS; print(VALID_TRANSITIONS[ApplicationState.AADHAAR_OTP])"` — new transition is reachable.
4. Manually trigger a transition in a script: create an app in `READY_FOR_PORTAL`, call `transition(app.id, ApplicationState.PORTAL_RUNNING)`, then `db.refresh(workflow)` and assert `workflow.current_node == "PORTAL_RUNNING"` and a `WorkflowEvent` row exists.
5. Trigger an EXCEPTION via worker exception path, then assert the only legal transition out is `→ resume_target` (not any other state).

---

## Definition of done

- `transition()` writes 4 rows atomically on every call.
- All 6 missing states are mapped in `VALID_TRANSITIONS`.
- RESUME bypass is gone; recovery uses explicit `resume_target`.
- Playwright worker no longer mutates state directly.
- New `workflow` repository exists.
- All existing tests pass + new ones added.

---

## CONTINUATION PROMPT — start Phase 04

```
Starting Phase 04 of the AINCURU × TAXLA remediation. Phase 03 is complete:
- transition() now writes Application + Workflow + WorkflowEvent + AuditLog in one txn.
- 6 missing states mapped in VALID_TRANSITIONS: AADHAAR_OTP, PAN_VERIFICATION,
  DATA_VERIFICATION, REGISTERED, DUPLICATE_PAN_DETECTED, UAM_NOT_FOUND.
- RESUME bypass replaced with EXCEPTION → resume_target (explicit, auditable).
- worker/playwright_agent.py uses transition() instead of direct mutation.
- New backend/app/repositories/workflow.py exists.
- test_state_machine.py extended; passes.

Read the full plan: documents/implementation phases/phase-04-validation-engine.md

Goal: Make validation_engine.py actually branch on confidence per
documents/19_document_processing.md:
- HIGH (confidence >= 0.85): auto-verify, transition VALIDATION -> NIC_REVIEW directly.
- MEDIUM (0.70-0.84): yellow flag, transition VALIDATION -> VALIDATION_REVIEW
  (notify reviewer; allow override via PATCH).
- LOW (<0.70): force manual review, transition VALIDATION -> HUMAN_REVIEW_REQUIRED.
Add the new VALIDATION_REVIEW + HUMAN_REVIEW_REQUIRED states to the state machine (if
not already added in Phase 03).
Implement actual validation_rules: PAN format, Aadhaar format, IFSC format, GSTIN format,
mobile (10-digit Indian), email, pincode (6-digit). Right now the validation_rules dict
advertised in the docstring doesn't exist.

After Phase 04 verification passes, paste the Phase 05 continuation prompt.

---

PHASE 05 CONTINUATION PROMPT:

Starting Phase 05 of the AINCURU × TAXLA remediation. Phase 04 is complete: the engine
branches on confidence (HIGH/MEDIUM/LOW) with explicit transitions; validation_rules dict
actually validates PAN, Aadhaar, IFSC, GSTIN, mobile, email, pincode.

Read the full plan: documents/implementation phases/phase-05-role-enforcement.md

Goal: Implement require_roles() on every API endpoint. Currently it's defined in
backend/app/core/security.py but never used. Apply the matrix from
documents/04_user_roles_and_permissions.md:
- SUPER_ADMIN: full access.
- BRANCH_ADMIN: full access within their branch.
- OPERATOR: can create apps, upload docs, verify OCR; CANNOT approve NIC; CANNOT do
  final submission.
- REVIEWER_AUDITOR: can approve NIC, authorize final submission; CANNOT upload initial
  docs / do data entry.
Add a branch-scope guard helper: assert application.branch_id == current_user.branch_id
(or current_user.role == SUPER_ADMIN). On mismatch return 403 (per doc 04) or 404 (per
doc 26) — pick one and document.
```