from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional, List


class MarketplaceListingResponse(BaseModel):
    id: UUID
    marketplace: str
    marketplace_sku: Optional[str]
    external_id: str
    marketplace_title: Optional[str]
    price: Optional[Decimal]
    currency: str
    listing_status: Optional[str]
    import_status: str
    product_variant_id: Optional[UUID]
    created_at: datetime
    marketplace_product_type: Optional[str]
    marketplace_url: Optional[str]
    listing_quality_score: Optional[Decimal] = None

    class Config:
        from_attributes = True

class MarketplaceListingDetailResponse(MarketplaceListingResponse):
    marketplace_description: Optional[str]
    marketplace_item_id: str
    marketplace_images: List[str] = []
    marketplace_customer_rating: Optional[str] = None
    marketplace_num_reviews: Optional[str] = None
    marketplace_keywords: List[str] = []
    marketplace_bullet_points: List[str] = []
    marketplace_customer_rating: Optional[str] = None
    brand: Optional[str] = None
    listing_quality_data: Optional[dict] = None

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
    images: List[str] = []
    customer_rating: Optional[str] = None
    num_reviews: Optional[str] = None
    keywords: List[str] = []
    bullet_points: List[str] = []
    brand: Optional[str] = None

    class Config:
        from_attributes = True


class BulkScrapeRequest(BaseModel):
    listing_ids: List[UUID]


class ScrapeResponse(BaseModel):
    message: str
    listing_id: Optional[UUID] = None
    count: Optional[int] = None

