import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Enum,
    Text,
    UniqueConstraint,
    Index,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.models.base import Base


# ========================
# ENUMS
# ========================

class OrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_SHIPPED = "PARTIALLY_SHIPPED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class OrderLineStatus(str, enum.Enum):
    CREATED = "CREATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


# ========================
# ORDER
# ========================

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    marketplace_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    marketplace: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    external_order_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    customer_order_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    order_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status_enum"),
        default=OrderStatus.CREATED,
        nullable=False,
        index=True,
    )

    # ========================
    # Customer Info
    # ========================

    customer_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    customer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    customer_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # ========================
    # Shipping
    # ========================

    shipping_address: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    shipping_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    estimated_ship_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    estimated_delivery_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ========================
    # Financial
    # ========================

    order_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    order_total: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )

    # ========================
    # Raw Data
    # ========================

    raw_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ========================
    # Shipping Label
    # ========================

    label_tracking_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    label_carrier: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    label_carrier_service_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    label_tracking_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # ========================
    # Metadata
    # ========================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ========================
    # Relationships
    # ========================

    organization = relationship("Organization")
    marketplace_account = relationship("MarketplaceAccount")

    lines = relationship(
        "OrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    status_logs = relationship(
        "OrderStatusLog",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    # ========================
    # Constraints
    # ========================

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "external_order_id",
            name="uq_org_marketplace_order",
        ),
        Index(
            "ix_orders_org_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_orders_org_marketplace",
            "organization_id",
            "marketplace",
        ),
        Index(
            "ix_orders_org_order_date",
            "organization_id",
            "order_date",
        ),
    )


# ========================
# ORDER LINE
# ========================

class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    line_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    external_sku: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    product_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    unit_price: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    shipping_charge: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    tax_amount: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    status: Mapped[OrderLineStatus] = mapped_column(
        Enum(OrderLineStatus, name="order_line_status_enum"),
        default=OrderLineStatus.CREATED,
        nullable=False,
        index=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ========================
    # Tracking
    # ========================

    tracking_carrier: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    tracking_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    tracking_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    ship_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    refund_amount: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    raw_line_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # ========================
    # Metadata
    # ========================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ========================
    # Relationships
    # ========================

    order = relationship("Order", back_populates="lines")
    organization = relationship("Organization")
    product_variant = relationship("ProductVariant")

    status_logs = relationship(
        "OrderStatusLog",
        back_populates="order_line",
        cascade="all, delete-orphan",
    )

    # ========================
    # Constraints
    # ========================

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "line_number",
            name="uq_order_line_number",
        ),
    )


# ========================
# ORDER STATUS LOG
# ========================

class OrderStatusLog(Base):
    __tablename__ = "order_status_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_lines.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    previous_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ========================
    # Relationships
    # ========================

    order = relationship("Order", back_populates="status_logs")
    order_line = relationship("OrderLine", back_populates="status_logs")
