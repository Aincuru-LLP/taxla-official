# AINCURU × TAXLA — USER ROLES & PERMISSIONS SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Security & Platform Engineering
version: 1.1
target_module: Authentication & Authorization Core
---

## 1. Access Control Model

Taxla utilizes **Role-Based Access Control (RBAC)** scoped dynamically by **Branch ID**. A user's privileges are a combination of their hierarchical `Role` and their geographic/organizational `Branch` assignment.

## 2. Core User Roles

### 2.1 Super Admin (`SUPER_ADMIN`)
- **Scope**: Global (Unrestricted by Branch ID).
- **Capabilities**: Can manage all users, branches, and system-wide configurations. Can view and mutate applications across all branches.

### 2.2 Branch Admin (`BRANCH_ADMIN`)
- **Scope**: Scoped to exactly one `Branch ID`.
- **Capabilities**: Can manage Operators and Reviewers within their branch. Can view all applications within their branch. Can configure branch-level overrides.

### 2.3 Operator (`OPERATOR`)
- **Scope**: Scoped to exactly one `Branch ID` and typically limited to `assigned_applications`.
- **Capabilities**: Can initiate new workflows, upload documents, review AI extraction results, and inject OTPs.
- **Restrictions**: Cannot approve NIC codes and cannot perform final submission approval.

### 2.4 Reviewer / Auditor (`REVIEWER`)
- **Scope**: Scoped to exactly one `Branch ID`.
- **Capabilities**: Authorized to approve sensitive state transitions. Can approve or reject AI-generated NIC codes. Can provide final authorization before Playwright submits data to the portal.
- **Restrictions**: Does not handle initial document upload or data entry.

## 3. API & JWT Authorization Mechanics

### 3.1 Token Structure
The `access_token` (JWT) payload must include:
```json
{
  "sub": "user_id_uuid",
  "email": "operator@taxla.com",
  "role": "OPERATOR",
  "branch_id": "branch_id_uuid",
  "exp": 1725062400
}
```

### 3.2 Endpoint Protection (FastAPI Dependencies)
- Every API route must explicitly define its allowed roles (e.g., `Depends(RoleChecker(["SUPER_ADMIN", "BRANCH_ADMIN"]))`).
- If an entity (like `Application`) is accessed, the backend MUST verify that `user.branch_id == application.branch_id` (unless `SUPER_ADMIN`).
- UI visibility is merely a convenience; the API is the absolute source of truth for authorization.

## 4. Immutable Audit Trail

Every state-mutating action performed by a user (e.g., `Approve NIC`, `Submit OTP`) must create a record in the `audit_logs` table capturing:
- `actor_id` (The User UUID)
- `action` (e.g., `NIC_APPROVED`)
- `metadata_json` (e.g., `{"selected_nic": "62011", "ai_confidence": 0.89}`)
- `timestamp`