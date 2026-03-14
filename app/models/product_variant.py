import uuid
from datetime import datetime
from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    String,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.models.base import Base


class ProductVariant(Base):
    __tablename__ = "product_variants"

    # ========================
    # Primary Identity
    # ========================
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

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ========================
    # Variant Attributes (MVP)
    # ========================
    color_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("colors.id"),
        nullable=True,
    )

    size_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sizes.id"),
        nullable=True,
    )

    # ========================
    # SKU
    # ========================
    sku: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    barcode: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ========================
    # Physical Attributes
    # ========================
    weight: Mapped[float | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )

    length: Mapped[float | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )

    width: Mapped[float | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )

    height: Mapped[float | None] = mapped_column(
        Numeric(10, 3),
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
    product = relationship(
        "Product",
        back_populates="variants",
    )

    media = relationship(
    "ProductMedia",
    back_populates="product_variant",
    cascade="all, delete-orphan",
    )

    marketplace_listings = relationship(
    "MarketplaceListing",
    back_populates="product_variant",
    cascade="all, delete-orphan",
    )

    organization = relationship("Organization")

    color = relationship("Color")
    size = relationship("Size")

    inventory = relationship(
        "Inventory",
        primaryjoin="ProductVariant.id == Inventory.product_variant_id",
        uselist=False,
        viewonly=True,
    )

    # ========================
    # Constraints
    # ========================
    __table_args__ = (
        # Prevent duplicate SKU per organization
        UniqueConstraint(
            "organization_id",
            "sku",
            name="uq_org_sku",
        ),

        # Prevent duplicate variant combinations per product
        UniqueConstraint(
            "product_id",
            "color_id",
            "size_id",
            name="uq_product_variant_combination",
        ),
    )
