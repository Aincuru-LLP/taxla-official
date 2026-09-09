# AINCURU × TAXLA — AUDIT LOGGING SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. The Principle of Immutability

Audit logs are the single source of truth for compliance. The `audit_logs` table is append-only. UPDATE and DELETE operations are strictly forbidden on this table.

## 2. Audit Log Structure

Every critical mutation writes a row to the database.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `application_id` | UUID | The context of the action |
| `user_id` | UUID | The human (or SYSTEM) that performed the action |
| `action` | String | e.g., `DOCUMENT_UPLOADED`, `NIC_APPROVED`, `WORKFLOW_FAILED` |
| `previous_state` | JSON | A snapshot of the data before mutation |
| `new_state` | JSON | A snapshot of the data after mutation |
| `ip_address` | String | Originating IP (from FastAPI request) |
| `created_at` | DateTime | Auto-generated timestamp |

## 3. Mandatory Audit Events

Code MUST generate an audit log for:
- State transitions (e.g., `DRAFT` -> `PROCESSING`).
- Data mutations (e.g., Operator corrects a PAN number manually).
- Approvals (e.g., Reviewer clicks "Submit to Portal").
- Security events (e.g., Failed login attempts, role changes).

## 4. Separation of Workflow vs. Audit

- `workflow_events` (table) tracks system progress (e.g., "Ollama started", "Playwright clicked button").
- `audit_logs` (table) tracks business compliance and human accountability (e.g., "Operator 123 approved PAN ABCDE").