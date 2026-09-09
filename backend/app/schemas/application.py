from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict
import uuid

# Base Address Schema (used for units and official address)
class AddressBase(BaseModel):
    flat: Optional[str] = None
    building: Optional[str] = None
    village_town: Optional[str] = None
    block: Optional[str] = None
    road_street: Optional[str] = None
    city: Optional[str] = None
    pin: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None

class OfficialAddressCreate(AddressBase):
    pass

class OfficialAddressResponse(AddressBase):
    id: uuid.UUID
    application_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)

class ApplicationUnitCreate(AddressBase):
    unit_name: str

class ApplicationUnitResponse(AddressBase):
    id: uuid.UUID
    application_id: uuid.UUID
    unit_name: str
    model_config = ConfigDict(from_attributes=True)

class ClientResponse(BaseModel):
    id: uuid.UUID
    business_name: str
    applicant_name: str
    mobile_number: str
    email: Optional[str] = None
    pan_number: str
    gender: Optional[str] = None
    social_category: Optional[str] = None
    divyang_status: Optional[bool] = None
    model_config = ConfigDict(from_attributes=True)

class ApplicationCreate(BaseModel):
    # This acts as the initial payload when POST /applications is called.
    branch_id: Optional[uuid.UUID] = None
    business_name: str
    applicant_name: str
    mobile_number: str
    email: Optional[str] = None
    pan_number: str
    aadhaar_number: str
    gender: Optional[str] = None
    social_category: Optional[str] = None
    divyang_status: Optional[bool] = False
    workflow_type: Optional[str] = "NEW_UDYAM"

class ApplicationUpdate(BaseModel):
    # This acts as the payload for PATCH /applications/{id} where operators can update details
    enterprise_type: Optional[str] = None
    social_category: Optional[str] = None
    
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    
    previous_em_ii_uam: Optional[str] = None
    uam_number: Optional[str] = None
    
    incorporation_date: Optional[datetime] = None
    business_commenced: Optional[bool] = None
    commencement_date: Optional[datetime] = None
    major_activity: Optional[str] = None
    
    male_employees: Optional[int] = None
    female_employees: Optional[int] = None
    other_employees: Optional[int] = None
    child_labour_declaration: Optional[bool] = None
    
    written_down_value: Optional[float] = None
    eligible_exclusions: Optional[float] = None
    net_investment: Optional[float] = None
    total_turnover: Optional[float] = None
    export_turnover: Optional[float] = None
    net_turnover: Optional[float] = None
    
    interested_in_gem: Optional[bool] = None
    interested_in_treds: Optional[bool] = None
    interested_in_ncs: Optional[bool] = None
    interested_in_nsic_b2b: Optional[bool] = None
    interested_in_in_domain: Optional[bool] = None
    
    district_industries_centre: Optional[str] = None
    
    official_address: Optional[OfficialAddressCreate] = None
    units: Optional[List[ApplicationUnitCreate]] = None

class ApplicationResponse(BaseModel):
    id: uuid.UUID
    application_number: str
    workflow_type: str
    status: str
    client_id: uuid.UUID
    branch_id: uuid.UUID

    # Financial/Details included
    enterprise_type: Optional[str] = None
    bank_name: Optional[str] = None
    net_investment: Optional[float] = None
    total_turnover: Optional[float] = None

    created_at: datetime
    updated_at: datetime

    client: Optional[ClientResponse] = None
    official_address: Optional[OfficialAddressResponse] = None
    units: List[ApplicationUnitResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Phase 11 — timeline endpoints
# ---------------------------------------------------------------------------
class AuditLogResponse(BaseModel):
    """One row of the immutable application audit log."""
    id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    application_id: Optional[uuid.UUID] = None
    action: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata_json: dict = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowEventResponse(BaseModel):
    """One workflow node transition event."""
    id: uuid.UUID
    application_id: uuid.UUID
    workflow_id: uuid.UUID
    node_key: str
    event_type: str
    status: str
    payload_json: Optional[dict] = None
    error_code: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
