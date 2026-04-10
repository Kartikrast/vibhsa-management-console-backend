from typing import List, Optional
from pydantic import BaseModel

from app.schemas.order import FromAddressRequest


class WalmartConnectRequest(BaseModel):
    seller_id: str
    client_id: str
    client_secret: str

class AmazonConnectRequest(BaseModel):
    seller_id: str
    client_id: str
    client_secret: str
    refresh_token: str
    region: str = "US"


class UpdateMarketplaceAccountRequest(BaseModel):
    default_from_address: FromAddressRequest | None = None
    default_return_address: FromAddressRequest | None = None


class WalmartItem(BaseModel):
    sku: Optional[str]
    productName: Optional[str]
    publishedStatus: Optional[str]
    lifecycleStatus: Optional[str]


class WalmartItemsResponse(BaseModel):
    items: List[WalmartItem]


class WalmartReportType(BaseModel):
    type: str
    name: str
    versions: List[str]


class WalmartReportRequestCreate(BaseModel):
    report_type: str
    report_version: str
    data_start_time: str  # ISO format datetime string
    data_end_time: str    # ISO format datetime string
    row_filters: Optional[dict] = None
    exclude_columns: Optional[List[str]] = None


class WalmartReportRequestResponse(BaseModel):
    id: str
    external_request_id: Optional[str]
    report_type: str
    report_version: str
    data_start_time: str
    data_end_time: str
    status: str
    download_url: Optional[str]
    expires_at: Optional[str]
    completed_at: Optional[str]
    failed_at: Optional[str]
    error: Optional[str]
    created_at: str
    updated_at: str


class WalmartReportRequestsList(BaseModel):
    reports: List[WalmartReportRequestResponse]
    total: int


class WalmartRateLimitErrorResponse(BaseModel):
    error: str = "rate_limit_exceeded"
    remaining_tokens: int
    max_tokens: int
    next_replenishment_time: Optional[str]
    retry_after_seconds: Optional[int]

class WalmartItemListingQualityRequest(BaseModel):
    sku: Optional[str] = None
    item_id: Optional[str] = None