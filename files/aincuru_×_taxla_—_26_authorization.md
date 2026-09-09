# AINCURU × TAXLA — AUTHORIZATION SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Security Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. The RBAC Model

Authorization in Taxla is multi-dimensional. A user's access is determined by their `Role` AND their `Branch ID` (Multi-tenancy).

### Roles
- **`SUPER_ADMIN`**: Can create branches, manage global configurations, view cross-branch metrics, and promote users.
- **`BRANCH_MANAGER`**: Can view all applications within their specific Branch. Can assign Operators.
- **`OPERATOR`**: Can only view and process Applications assigned to them (or unassigned in their Branch pool). Cannot bypass final reviews.
- **`REVIEWER`**: A specialized compliance role required to click "Approve" before automated submission.

## 2. Enforcement (Server-Side)

UI hiding is not security. Authorization is strictly enforced in the FastAPI layer via Dependency Injection.

**Example Implementation Rule**:
```python
@router.get("/applications/{app_id}")
async def get_application(
    app_id: UUID, 
    current_user: User = Depends(require_role(["OPERATOR", "BRANCH_MANAGER"]))
):
    # 1. Fetch application
    # 2. Assert application.branch_id == current_user.branch_id
    # 3. If mismatch, throw 403 Forbidden
```

## 3. Cross-Tenant Boundaries

An `OPERATOR` in Branch A must receive a `404 Not Found` or `403 Forbidden` when attempting to fetch an `application_id` belonging to Branch B, even if they possess a valid JWT.

## 4. Audit Logging

Every state-mutating action (POST/PUT/DELETE) must log the `user_id` of the actor to the `audit_logs` table, associating it with the `application_id` and the action performed.