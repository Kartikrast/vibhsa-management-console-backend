from pydantic import BaseModel
from uuid import UUID


class LinkExistingListingRequest(BaseModel):
    product_variant_id: UUID

class GenerateFromListingRequest(BaseModel):
    category_id: UUID
    subcategory_id: UUID
    subsubcategory_id: UUID
    product_type_id: UUID
    material_id: UUID
    color_id: UUID
    size_id: UUID

class ListingLinkResponse(BaseModel):
    message: str
    product_variant_id: UUID
    internal_sku: str
