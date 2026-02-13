import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.models.base import Base


class GoogleTaxonomy(Base):
    __tablename__ = "google_taxonomies"

    # =========================
    # Primary Key
    # =========================
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Google official taxonomy numeric ID
    google_taxonomy_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
    )

    # Full breadcrumb path
    # Example:
    # "Home & Garden > Decor > Home Decor > Candle Holders"
    full_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Depth level (number of segments)
    level_depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Whether this is a leaf node
    # Leaf nodes are typically used for listing products
    is_leaf: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # =========================
    # Metadata
    # =========================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "google_taxonomy_id",
            name="uq_google_taxonomy_id",
        ),
    )
