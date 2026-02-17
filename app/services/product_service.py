import hashlib
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory
from app.models.product_counter import ProductTypeCounter


# ============================
# SHA256 Signature Generator
# ============================
def generate_product_signature(
    organization_id,
    category_id,
    subcategory_id,
    subsubcategory_id,
    product_type_id,
    material_id,
):
    raw_string = (
        f"{organization_id}|"
        f"{category_id}|"
        f"{subcategory_id}|"
        f"{subsubcategory_id or ''}|"
        f"{product_type_id}|"
        f"{material_id}"
    )

    return hashlib.sha256(raw_string.encode()).hexdigest()


# ============================
# Product Creation Service
# ============================
def create_product(
    db: Session,
    organization_id,
    category,
    subcategory,
    subsubcategory,
    product_type,
    material,
    color,
    size,
    gtin: str | None = None,
):
    try:

        # ----------------------------------
        # 1️⃣ Generate SHA256 signature
        # ----------------------------------
        signature = generate_product_signature(
            organization_id=organization_id,
            category_id=category.id,
            subcategory_id=subcategory.id,
            subsubcategory_id=subsubcategory.id if subsubcategory else None,
            product_type_id=product_type.id,
            material_id=material.id,
        )

        # ----------------------------------
        # 2️⃣ Lock ProductTypeCounter
        # ----------------------------------
        stmt = (
            select(ProductTypeCounter)
            .where(
                ProductTypeCounter.organization_id == organization_id,
                ProductTypeCounter.product_type_id == product_type.id,
            )
            .with_for_update()
        )

        counter = db.execute(stmt).scalar_one_or_none()

        if not counter:
            counter = ProductTypeCounter(
                organization_id=organization_id,
                product_type_id=product_type.id,
                current_value=0,
            )
            db.add(counter)
            db.flush()

        counter.current_value += 1
        product_code = counter.current_value

        # ----------------------------------
        # 3️⃣ Create Product
        # ----------------------------------
        product = Product(
            organization_id=organization_id,
            category_id=category.id,
            subcategory_id=subcategory.id,
            subsubcategory_id=subsubcategory.id if subsubcategory else None,
            product_type_id=product_type.id,
            material_id=material.id,
            product_code=product_code,
            product_signature=signature,
            gtin=gtin,
        )

        db.add(product)
        db.flush()

        # ----------------------------------
        # 4️⃣ Generate SKU
        # ----------------------------------
        sku = (
            f"{category.short_code}"
            f"{subcategory.short_code}"
            f"{subsubcategory.short_code if subsubcategory else ''}"
            f"{product_type.short_code}"
            f"{product_code}"
            f"{color.short_code if color else ''}"
            f"{size.short_code if size else ''}"
        )

        # ----------------------------------
        # 5️⃣ Create Variant
        # ----------------------------------
        variant = ProductVariant(
            organization_id=organization_id,
            product_id=product.id,
            color_id=color.id if color else None,
            size_id=size.id if size else None,
            sku=sku,
        )

        db.add(variant)
        db.flush()

        # ----------------------------------
        # 6️⃣ Create Inventory (default location)
        # ----------------------------------
        inventory = Inventory(
            organization_id=organization_id,
            product_variant_id=variant.id,
            location_name="default",
            quantity_available=0,
            quantity_reserved=0,
        )

        db.add(inventory)

        return product

    except IntegrityError:
        db.rollback()
        raise ValueError("Duplicate product detected or SKU conflict")

def create_variant_for_existing_product(
    db: Session,
    organization_id,
    product,
    category,
    subcategory,
    subsubcategory,
    product_type,
    color,
    size,
):
    sku = (
        f"{category.short_code}"
        f"{subcategory.short_code}"
        f"{subsubcategory.short_code if subsubcategory else ''}"
        f"{product_type.short_code}"
        f"{product.product_code}"
        f"{color.short_code if color else ''}"
        f"{size.short_code if size else ''}"
    )

    variant = ProductVariant(
        organization_id=organization_id,
        product_id=product.id,
        color_id=color.id if color else None,
        size_id=size.id if size else None,
        sku=sku,
    )

    db.add(variant)
    db.flush()

    inventory = Inventory(
        organization_id=organization_id,
        product_variant_id=variant.id,
        location_name="default",
        quantity_available=0,
        quantity_reserved=0,
    )

    db.add(inventory)

    return variant
