from pydantic import BaseModel, model_validator
from uuid import UUID
from typing import Optional


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
    initial_quantity: Optional[int] = None
    sync_inventory_from_marketplace: bool = False

    @model_validator(mode="after")
    def validate_inventory_options(self):
        if self.sync_inventory_from_marketplace and self.initial_quantity is not None:
            raise ValueError(
                "Cannot provide initial_quantity when sync_inventory_from_marketplace is True"
            )
        if self.initial_quantity is not None and self.initial_quantity < 0:
            raise ValueError("initial_quantity must be non-negative")
        return self

class ListingLinkResponse(BaseModel):
    message: str
    product_variant_id: UUID
    internal_sku: str

class InventoryUpdateRequest(BaseModel):
    quantity_available: int

    @model_validator(mode="after")
    def validate_quantity(self):
        if self.quantity_available < 0:
            raise ValueError("quantity_available must be non-negative")
        return self

class UpdateMarketplaceInventoryRequest(BaseModel):
    new_quantity: int

    @model_validator(mode="after")
    def validate_new_quantity(self):
        if self.new_quantity < 0:
            raise ValueError("new_quantity must be non-negative")
        return self

class MarketplaceInventoryResponse(BaseModel):
    marketplace_quantity: int
    source: str

class ListingInventoryResponse(BaseModel):
    internal_quantity_available: int
    internal_quantity_reserved: int
    marketplace_quantity: Optional[int] = None
    marketplace_source: Optional[str] = None
