import uuid
from datetime import datetime
from sqlalchemy import (
    ForeignKey,
    Integer,
    UniqueConstraint,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.models.base import Base


class Inventory(Base):
    __tablename__ = "inventory"

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

    product_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ========================
    # Location (MVP Simple)
    # ========================
    location_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="default",
    )

    # ========================
    # Quantities
    # ========================
    quantity_available: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    quantity_reserved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
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

    product_variant = relationship("ProductVariant")

    # ========================
    # Constraints
    # ========================
    __table_args__ = (
        # Prevent duplicate location entry for same variant
        UniqueConstraint(
            "organization_id",
            "product_variant_id",
            "location_name",
            name="uq_inventory_variant_location",
        ),
    )
