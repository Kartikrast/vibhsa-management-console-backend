import uuid
from datetime import datetime
from sqlalchemy import (
    ForeignKey,
    Integer,
    UniqueConstraint,
    Text,
    String,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.models.base import Base


class Product(Base):
    __tablename__ = "products"

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

    # ========================
    # Taxonomy Structure
    # ========================
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=False,
    )

    subcategory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subcategories.id"),
        nullable=False,
    )

    subsubcategory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subsubcategories.id"),
        nullable=True,
    )

    product_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_types.id"),
        nullable=False,
    )

    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("materials.id"),
        nullable=False,
    )

    # ========================
    # Serial Identity
    # ========================
    product_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    product_signature: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    gtin: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    # ========================
    # PIM Content (NEW)
    # ========================

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    bullet_points: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    meta_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    meta_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    seo_keywords: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    product_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "DRAFT",
            "ACTIVE",
            "PUBLISHED",
            "ARCHIVED",
            name="product_status_enum",
        ),
        default="DRAFT",
        nullable=False,
        index=True,
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

    category = relationship("Category")
    subcategory = relationship("SubCategory")
    subsubcategory = relationship("SubSubCategory")

    product_type_rel = relationship("ProductType")
    material = relationship("Material")

    variants = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    media = relationship(
        "ProductMedia",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # ========================
    # Constraints
    # ========================
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "product_type_id",
            "product_code",
            name="uq_org_product_type_code",
        ),
        UniqueConstraint(
            "organization_id",
            "product_signature",
            name="uq_org_product_signature",
        ),
        UniqueConstraint(
            "organization_id",
            "gtin",
            name="uq_product_gtin_per_org",
        ),
    )
