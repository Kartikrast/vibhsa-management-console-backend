from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


# ========================
# ORDER LINE SCHEMAS
# ========================

class OrderLineResponse(BaseModel):
    id: UUID
    order_id: UUID
    line_number: str
    external_sku: str | None = None
    product_name: str | None = None
    product_variant_id: UUID | None = None
    quantity: int
    unit_price: float | None = None
    shipping_charge: float | None = None
    tax_amount: float | None = None
    status: str
    cancellation_reason: str | None = None
    tracking_carrier: str | None = None
    tracking_number: str | None = None
    tracking_url: str | None = None
    ship_date: datetime | None = None
    refund_amount: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ========================
# ORDER SCHEMAS
# ========================

class OrderListResponse(BaseModel):
    id: UUID
    marketplace: str
    external_order_id: str
    customer_order_id: str | None = None
    order_type: str | None = None
    status: str
    customer_name: str | None = None
    order_date: datetime | None = None
    order_total: float | None = None
    currency: str = "USD"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderDetailResponse(BaseModel):
    id: UUID
    organization_id: UUID
    marketplace_account_id: UUID
    marketplace: str
    external_order_id: str
    customer_order_id: str | None = None
    order_type: str | None = None
    status: str
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    shipping_address: dict | None = None
    shipping_method: str | None = None
    estimated_ship_date: datetime | None = None
    estimated_delivery_date: datetime | None = None
    order_date: datetime | None = None
    order_total: float | None = None
    currency: str = "USD"
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    lines: list[OrderLineResponse] = []

    model_config = {"from_attributes": True}


# ========================
# ACTION REQUEST SCHEMAS
# ========================

class ShipLineRequest(BaseModel):
    line_id: UUID
    carrier: str
    tracking_number: str
    tracking_url: str | None = None


class ShipOrderRequest(BaseModel):
    lines: list[ShipLineRequest]


class CancelLineRequest(BaseModel):
    line_id: UUID
    reason: str = "SELLER_CANCEL_OUT_OF_STOCK"


class CancelOrderRequest(BaseModel):
    lines: list[CancelLineRequest]


class RefundLineRequest(BaseModel):
    line_id: UUID
    amount: float


class RefundOrderRequest(BaseModel):
    lines: list[RefundLineRequest]


class LinkOrderLineRequest(BaseModel):
    product_variant_id: UUID


# ========================
# SHIPPING LABEL SCHEMAS
# ========================

class BoxItemRequest(BaseModel):
    sku: str
    quantity: int = 1
    country_of_origin: str = "US"
    harmonized_code: str = ""


class FromAddressRequest(BaseModel):
    contact_name: str
    company_name: str = ""
    address_line1: str
    address_line2: str = ""
    city: str
    state: str
    postal_code: str
    country: str = "US"
    phone: str = ""


class CreateShippingLabelRequest(BaseModel):
    package_type: str = "CUSTOM_PACKAGE"
    box_weight: float = 1
    box_length: float = 10
    box_width: float = 8
    box_height: float = 4
    box_dimension_unit: str = "IN"
    box_weight_unit: str = "LB"
    box_items: list[BoxItemRequest]
    from_address: FromAddressRequest


class DownloadShippingLabelRequest(BaseModel):
    carrier: str
    tracking_number: str


class VoidShippingLabelRequest(BaseModel):
    carrier: str
    tracking_number: str


# ========================
# STATUS LOG SCHEMA
# ========================

class OrderStatusLogResponse(BaseModel):
    id: UUID
    order_id: UUID
    order_line_id: UUID | None = None
    previous_status: str | None = None
    new_status: str
    source: str
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ========================
# IMPORT RESPONSE
# ========================

class OrderImportResponse(BaseModel):
    imported: int
    updated: int
    skipped: int
    message: str
