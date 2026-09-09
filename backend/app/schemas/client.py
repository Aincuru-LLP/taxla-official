"""Phase 14 — Client directory schemas.

Read-only responses for the `/clients` endpoints. Mirrors the
``Client`` model minus ``aadhaar_number_hash`` (the hash is internal-only;
clients never appear on a list view).
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class ClientResponse(BaseModel):
    id: UUID
    business_name: str
    applicant_name: str
    mobile_number: str
    email: str | None = None
    pan_number: str
    gender: str | None = None
    social_category: str | None = None
    divyang_status: bool | None = None
    branch_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientWithStatsResponse(ClientResponse):
    """Client + roll-up stats for the directory table.

    ``application_count`` is the number of applications that point at
    this client (any status). ``active_count`` is the subset that is
    still in-flight (anything that hasn't reached a terminal state).
    """

    application_count: int
    active_count: int
