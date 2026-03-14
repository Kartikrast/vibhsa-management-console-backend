from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# ==============================
# Simple Nested Taxonomy Schema
# ==============================

class SimpleTaxonomyResponse(BaseModel):
    id: UUID
    name: str
    short_code: str

    class Config:
        from_attributes = True


# ==============================
# Inventory Schema
# ==============================

class InventoryResponse(BaseModel):
    quantity_available: int
    quantity_reserved: int
    location_name: str

    class Config:
        from_attributes = True


# ==============================
# Media Schema
# ==============================

class ProductMediaResponse(BaseModel):
    id: UUID
    media_type: str
    media_url: str
    display_order: int
    is_primary: bool

    class Config:
        from_attributes = True


# ==============================
# Marketplace Summary Schema
# ==============================

class MarketplaceListingSummaryResponse(BaseModel):
    id: UUID
    marketplace: str
    import_status: str
    sync_status: str
    listing_status: str
    last_feed_status: Optional[str] = None
    last_feed_error: Optional[str] = None

    class Config:
        from_attributes = True


# ==============================
# Variant Schema
# ==============================

class ProductVariantResponse(BaseModel):
    id: UUID
    sku: str

    color: Optional[SimpleTaxonomyResponse] = None
    size: Optional[SimpleTaxonomyResponse] = None

    inventory: Optional[InventoryResponse] = None
    media: List[ProductMediaResponse] = []
    marketplace_listings: List[MarketplaceListingSummaryResponse] = []

    class Config:
        from_attributes = True


# ==============================
# Product Detail Schema
# ==============================

class ProductDetailResponse(BaseModel):
    id: UUID
    title: Optional[str]
    description: Optional[str]
    bullet_points: Optional[List[str]]
    meta_title: Optional[str]
    meta_description: Optional[str]
    seo_keywords: Optional[List[str]]
    product_type: Optional[str] = None
    status: str

    gtin: Optional[str]

    category: SimpleTaxonomyResponse
    subcategory: SimpleTaxonomyResponse
    subsubcategory: Optional[SimpleTaxonomyResponse] = None
    product_type_rel: SimpleTaxonomyResponse = Field(validation_alias="product_type_rel")
    material: SimpleTaxonomyResponse

    variants: List[ProductVariantResponse]

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==============================
# Product List Schema
# ==============================

class ProductListItemResponse(BaseModel):
    id: UUID
    title: Optional[str]
    status: str
    gtin: Optional[str]
    total_inventory: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    data: List[ProductListItemResponse]
    total: int
    page: int
    limit: int


class ProductStatusEnum(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class UpdateProductRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    bullet_points: Optional[List[str]] = None
    meta_title: Optional[str] = Field(None, max_length=500)
    meta_description: Optional[str] = None
    seo_keywords: Optional[List[str]] = None
    status: Optional[ProductStatusEnum] = None
    gtin: Optional[str] = Field(None, max_length=50)

class ReorderMediaRequest(BaseModel):
    ordered_media_ids: list[UUID]    