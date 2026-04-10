from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    organization_name: str
    invite_token: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class GoogleAuthRequest(BaseModel):
    token: str
    organization_name: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str  # user_id (UUID as string)
    org_id: str  # organization_id (UUID as string)
    role: str
    exp: int

class OrganizationInfo(BaseModel):
    id: UUID
    name: str
    slug: str

    class Config:
        from_attributes = True


class OrganizationListItem(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str
    is_current: bool = False

    class Config:
        from_attributes = True


class SwitchOrgRequest(BaseModel):
    organization_id: UUID


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CreateOrgRequest(BaseModel):
    name: str


class CreateOrgResponse(BaseModel):
    organization: OrganizationInfo
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: UUID
    email: EmailStr
    auth_provider: str
    organization: OrganizationInfo
    role: str
    organizations: list[OrganizationListItem] = []
