from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID

class UserLoginRequest(BaseModel):
    username: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    branch_id: Optional[UUID] = None
    status: str

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshResponse(BaseModel):
    """Response shape for /auth/refresh.

    The rotated refresh token is set as an HttpOnly cookie by the response
    headers; only the new short-lived access token comes back in the body.
    """

    access_token: str
    token_type: str = "bearer"
