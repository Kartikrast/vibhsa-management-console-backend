from datetime import datetime

from pydantic import BaseModel
from uuid import UUID


class ProductCreateRequest(BaseModel):
    category_id: UUID
    subcategory_id: UUID
    subsubcategory_id: UUID | None = None

    product_type_id: UUID
    material_id: UUID

    color_id: UUID | None = None
    size_id: UUID | None = None


class ProductResponse(BaseModel):
    id: UUID
    product_code: int
    created_at: datetime

    class Config:
        from_attributes = True

class VariantResponse(BaseModel):
    id: UUID
    sku: str
    color: str | None
    size: str | None
    quantity_available: int

    class Config:
        from_attributes = True

class ProductListResponse(BaseModel):
    id: UUID
    product_code: int
    category: str
    product_type: str
    material: str
    created_at: datetime
    variants: list[VariantResponse]

    class Config:
        from_attributes = True
