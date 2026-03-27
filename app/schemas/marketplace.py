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