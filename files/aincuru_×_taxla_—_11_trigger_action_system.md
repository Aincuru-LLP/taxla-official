# AINCURU × TAXLA — TRIGGER & ACTION SYSTEM SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Workflow Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. System Objective

To provide a decoupled mechanism where state mutations (Triggers) automatically dispatch predefined background tasks (Actions) without tangling business logic directly into FastAPI route handlers.

## 2. Event Dispatch Architecture

When an API endpoint succeeds, it emits an internal Domain Event. The `EventDispatcher` routes this event to the corresponding Action Handler (usually pushing a job to Redis).

### Supported Triggers (V1)
- `DOCUMENT_UPLOADED` -> Triggers `Action.RunOCR`
- `DATA_REVIEW_APPROVED` -> Triggers `Action.SuggestNIC`
- `NIC_REVIEW_APPROVED` -> Triggers `Action.StartPortalAutomation`
- `OTP_SUBMITTED` -> Triggers `Action.ResumePortalAutomation`

## 3. Action Contract Specification

Every Action must be strictly typed and registered:
- **`ActionName`**: e.g., `START_PORTAL_AUTOMATION`
- **`PayloadSchema`**: Requires `application_id` and `user_id` (for audit logging).
- **`Permissions`**: Validates if the triggering user actually has rights to initiate this background task.
- **`Queue`**: Designates which Redis queue handles this (e.g., `q_heavy_ai`, `q_browser`, `q_default`).

## 4. Rule of Strict Validation

An LLM can never dispatch an Action. Only authenticated HTTP API requests or the internal Workflow Engine's state transitions can emit Triggers. Actions must re-validate the current state of the application before executing (e.g., `Action.StartPortalAutomation` must verify that `application.status == NIC_REVIEW_APPROVED` before launching Playwright, avoiding race conditions).