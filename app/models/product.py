import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime, String

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

    # SHA256 fingerprint (64 char hex)
    product_signature: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
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

    product_type = relationship("ProductType")
    material = relationship("Material")

    variants = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # ========================
    # Constraints
    # ========================
    __table_args__ = (
        # Prevent duplicate product_code per org per product type
        UniqueConstraint(
            "organization_id",
            "product_type_id",
            "product_code",
            name="uq_org_product_type_code",
        ),
        # Prevent duplicate conceptual products
        UniqueConstraint(
            "organization_id",
            "product_signature",
            name="uq_org_product_signature",
        ),
    )
