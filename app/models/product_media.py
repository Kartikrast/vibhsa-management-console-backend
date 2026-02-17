import uuid
from datetime import datetime
from sqlalchemy import (
    ForeignKey,
    Boolean,
    Integer,
    String,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.models.base import Base


class ProductMedia(Base):
    __tablename__ = "product_media"

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
    # Media Info
    # ========================
    media_type: Mapped[str] = mapped_column(
        Enum(
            "IMAGE",
            "VIDEO",
            name="media_type_enum",
        ),
        nullable=False,
    )

    file_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ========================
    # Metadata
    # ========================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # ========================
    # Relationships
    # ========================
    product_variant = relationship(
        "ProductVariant",
        back_populates="media",
    )
