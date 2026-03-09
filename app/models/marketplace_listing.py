import uuid
from datetime import datetime
from sqlalchemy import (
    ForeignKey,
    UniqueConstraint,
    String,
    Numeric,
    Enum,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
import enum

from app.models.base import Base


# ========================
# IMPORT STATUS ENUM
# ========================

class ImportStatus(str, enum.Enum):
    UNLINKED = "UNLINKED"
    LINKED = "LINKED"
    ARCHIVED = "ARCHIVED"


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

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


    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ========================
    # External Identity
    # ========================

    marketplace: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    marketplace_sku: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Optional future matching
    gtin: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # ========================
    # Commercial Data
    # ========================

    price: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
    )

    marketplace_product_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ========================
    # Marketplace Content Overrides (NEW)
    # ========================

    override_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    override_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    override_bullet_points: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )


    # ========================
    # Status Management
    # ========================

    import_status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, name="import_status_enum"),
        default=ImportStatus.UNLINKED,
        nullable=False,
        index=True,
    )

    listing_status: Mapped[str] = mapped_column(
        String(50),
        default="published",
        nullable=False,
    )

    sync_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )

    # ========================
    # Raw Payload
    # ========================

    raw_payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
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
    product_variant = relationship(
        "ProductVariant",
        back_populates="marketplace_listings",
        )

    # ========================
    # Constraints
    # ========================

    __table_args__ = (
        # Prevent duplicate import of same listing
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "external_id",
            name="uq_external_listing_per_org",
        ),
    )
