import uuid
from datetime import datetime
from sqlalchemy import (
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.models.base import Base


class MarketplaceAccount(Base):
    __tablename__ = "marketplace_accounts"

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

    marketplace: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # e.g., "walmart", "amazon"

    seller_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    region: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="US",
        server_default="US",
    )

    client_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    client_secret: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    access_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    refresh_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    default_from_address: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    default_return_address: Mapped[dict | None] = mapped_column(
        JSONB,
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

    # Relationships
    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "marketplace",
            name="uq_org_marketplace",
        ),
        Index("ix_marketplace_org", "organization_id", "marketplace"),
    )
