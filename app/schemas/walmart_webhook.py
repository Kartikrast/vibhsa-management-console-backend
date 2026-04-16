from typing import List, Optional, Any
from pydantic import BaseModel


# ── Request schemas ──

class WalmartAuthDetails(BaseModel):
    authMethod: str = "BASIC_AUTH"
    userName: Optional[str] = None
    password: Optional[str] = None
    authHeaderName: str = "Authorization"
    # HMAC fields
    clientSecret: Optional[str] = None
    # OAUTH fields
    authUrl: Optional[str] = None
    headers: Optional[dict] = None


class WalmartSubscriptionEventCreate(BaseModel):
    eventType: str
    eventVersion: str = "V1"
    resourceName: str
    eventUrl: Optional[str] = None  # if None, service fills from settings
    authDetails: Optional[WalmartAuthDetails] = None  # if None, service fills BASIC_AUTH from settings


class WalmartSubscriptionCreateRequest(BaseModel):
    events: List[WalmartSubscriptionEventCreate]


class WalmartSubscriptionUpdateRequest(BaseModel):
    eventType: Optional[str] = None
    eventVersion: Optional[str] = None
    resourceName: Optional[str] = None
    eventUrl: Optional[str] = None
    authDetails: Optional[WalmartAuthDetails] = None
    status: Optional[str] = None  # ACTIVE or INACTIVE


class WalmartTestNotificationRequest(BaseModel):
    eventType: str
    eventVersion: str = "V1"
    resourceName: str
    eventUrl: Optional[str] = None  # if None, service fills from settings


# ── Response schemas ──

class WalmartEventTypeItem(BaseModel):
    eventType: Optional[str] = None
    eventVersion: Optional[str] = None
    resourceName: Optional[str] = None
    description: Optional[str] = None


class WalmartSubscriptionResponse(BaseModel):
    subscriptionId: Optional[str] = None
    eventType: Optional[str] = None
    eventVersion: Optional[str] = None
    resourceName: Optional[str] = None
    eventUrl: Optional[str] = None
    status: Optional[str] = None
    authDetails: Optional[dict] = None
    createdDate: Optional[str] = None
    updatedDate: Optional[str] = None


class WalmartWebhookEventResponse(BaseModel):
    id: str
    event_id: str
    event_type: str
    event_version: str
    resource_name: str
    payload: Any
    status: str
    error: Optional[str] = None
    processed_at: Optional[str] = None
    created_at: str
