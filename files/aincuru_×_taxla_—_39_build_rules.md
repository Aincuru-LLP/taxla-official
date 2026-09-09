# AINCURU × TAXLA — STRICT BUILD RULES & CHECKLISTS

---
status: APPROVED SPECIFICATION
owner: Engineering Leadership
version: 1.1
target_module: ALL
---

## 1. Source of Truth Hierarchy

When conflicts arise, resolution flows strictly downward:
```text
00_MASTER_PLAN.md (Supreme Authority)
↓
05_SYSTEM_ARCHITECTURE.md (Structural Laws)
↓
08_DATABASE_SCHEMA.md & 30_API_SPEC.md (Data Contracts)
↓
13_STATE_MACHINE.md (Business Logic)
↓
All other feature specifications
```

## 2. Non-Negotiable AI/LLM Rules

- **Never Trust AI Arguments Blindly**: All JSON outputs from Ollama must be parsed and strictly validated through Pydantic models before being written to the database.
- **Fail Closed**: If an LLM returns malformed JSON or hallucinates an invalid NIC code format, the extraction step MUST fail, alert the operator, and pause the workflow. Do NOT attempt to silently fix or ignore the error.
- **No Direct Mutation**: AI cannot directly update the `Application` canonical state. AI only writes to `extracted_data` or `nic_suggestions` for human review.

## 3. Strict Coding Standards

- **Backend**: 
  - FastAPI routes must contain zero business logic. Routes only parse input and call `Services`.
  - Database queries must be async (`asyncpg` / `aiosqlite`). 
  - No `SELECT *`. Explicitly select required columns.
- **Frontend**:
  - All API responses must be validated against `Zod` schemas.
  - Server State (React Query) must be strictly separated from UI State (Zustand / `useState`).
- **Dependencies**: Do NOT add new `pip` or `npm` packages without explicit justification. Avoid heavy libraries for trivial problems.

## 4. Task Completion & Verification Checklist

Before marking ANY feature as complete, the following MUST be verified:
- [ ] **State Machine Integrity**: Does this feature bypass any valid state transitions? (If yes -> REJECT).
- [ ] **Audit Logs**: Does this feature mutate state? Did it write a corresponding `audit_log` event? (If no -> REJECT).
- [ ] **Error Boundaries**: Are network failures (e.g., Udyam Portal down) caught and safely retried without crashing the worker?
- [ ] **RBAC**: Is the API endpoint protected by a JWT token and a Role check?
- [ ] **No Dead Ends**: If a task fails, is the operator notified in the UI?

## 5. The Ambiguity Rule

**STOP AND ASK.** If a requirement conflicts with the Database Schema, or if a frontend layout is missing data from the API, DO NOT invent a workaround. Stop, flag the inconsistency, and update the specifications before writing code.