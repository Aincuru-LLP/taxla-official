"""Phase 14 — Admin-facing user listing schemas.

Mirrors ``UserResponse`` minus anything that would leak secrets
(no password hash, no security-sensitive fields). Adds a ``last_active``
field computed from the audit log so the directory is useful as a
"who's been doing what" view.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserListResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    branch_id: UUID | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    last_active: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
