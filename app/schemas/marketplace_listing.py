from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional


class MarketplaceListingResponse(BaseModel):
    id: UUID
    marketplace: str
    marketplace_sku: Optional[str]
    external_id: str
    title: Optional[str]
    price: Optional[Decimal]
    currency: str
    listing_status: Optional[str]
    import_status: str
    product_variant_id: Optional[UUID]
    created_at: datetime
    marketplace_product_type: Optional[str]
    url: Optional[str]

    class Config:
        from_attributes = True

class ImportResponse(BaseModel):
    imported: int
    updated: int
    skipped: int = 0
    message: Optional[str] = None

class LinkListingRequest(BaseModel):
    product_variant_id: UUID

class MarketplaceInfoResponse(BaseModel):
    marketplace: str
    marketplace_sku: Optional[str]
    external_id: str
    title: Optional[str]
    price: Optional[Decimal]
    currency: str
    url: Optional[str]
    marketplace_product_type: Optional[str]
    import_status: str
    gtin: Optional[str]
    listing_status: Optional[str]
    inventory_quantity: Optional[int]

    class Config:
        from_attributes = True

