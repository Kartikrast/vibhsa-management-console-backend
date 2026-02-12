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


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

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

    marketplace_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_accounts.id", ondelete="CASCADE"),
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
    # Marketplace Data
    # ========================
    marketplace: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # e.g. "walmart"

    marketplace_sku: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    marketplace_item_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    price: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )

    listing_status: Mapped[str] = mapped_column(
        String(50),
        default="draft",  # draft, published, paused, archived
        nullable=False,
    )

    sync_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",  # pending, synced, failed
        nullable=False,
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

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
    product_variant = relationship("ProductVariant")

    # ========================
    # Constraints
    # ========================
    __table_args__ = (
        # Prevent same variant being listed twice on same marketplace account
        UniqueConstraint(
            "marketplace_account_id",
            "product_variant_id",
            name="uq_listing_variant_per_marketplace",
        ),
    )
