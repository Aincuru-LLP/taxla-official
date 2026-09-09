from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID

class DocumentResponse(BaseModel):
    id: UUID
    application_id: UUID
    type: str
    file_name: str
    mime_type: str
    size_bytes: int
    ocr_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
