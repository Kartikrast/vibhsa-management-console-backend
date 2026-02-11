from typing import List, Optional
from pydantic import BaseModel


class WalmartConnectRequest(BaseModel):
    seller_id: str
    client_id: str
    client_secret: str

class WalmartItem(BaseModel):
    sku: Optional[str]
    productName: Optional[str]
    publishedStatus: Optional[str]
    lifecycleStatus: Optional[str]


class WalmartItemsResponse(BaseModel):
    items: List[WalmartItem]