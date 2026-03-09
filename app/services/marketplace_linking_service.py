from sqlalchemy.orm import Session
from app.utils.gtin import normalize_gtin
from app.models.product import Product
from app.models.marketplace_listing import MarketplaceListing
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory
from fastapi import HTTPException
from uuid import UUID
from datetime import datetime, timezone
from app.services.product_service import (
    create_product,
    create_variant_for_existing_product,
    generate_product_signature,
)



def link_existing_listing(
    db: Session,
    organization_id: UUID,
    listing_id: UUID,
    product_variant_id: UUID,
):
    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == listing_id,
        MarketplaceListing.organization_id == organization_id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.import_status != "UNLINKED":
        raise HTTPException(status_code=400, detail="Listing already linked")

    variant = db.query(ProductVariant).filter(
        ProductVariant.id == product_variant_id,
        ProductVariant.organization_id == organization_id,
    ).first()

    if not variant:
        raise HTTPException(status_code=404, detail="Product variant not found")

    # Ensure variant not already linked for this marketplace account
    existing_link = db.query(MarketplaceListing).filter(
        MarketplaceListing.marketplace_account_id == listing.marketplace_account_id,
        MarketplaceListing.product_variant_id == product_variant_id,
    ).first()

    if existing_link:
        raise HTTPException(
            status_code=400,
            detail="Variant already linked to another listing on this marketplace account",
        )

    listing.product_variant_id = product_variant_id
    listing.import_status = "LINKED"
    listing.updated_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "message": "Listing linked successfully",
        "product_variant_id": product_variant_id,
        "internal_sku": variant.sku,
    }



def generate_internal_from_listing(
    db: Session,
    organization_id,
    listing_id,
    category,
    subcategory,
    subsubcategory,
    product_type,
    material,
    color,
    size,
):

    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == listing_id,
        MarketplaceListing.organization_id == organization_id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.import_status != "UNLINKED":
        raise HTTPException(status_code=400, detail="Listing already linked")

    # ----------------------------------
    # 1️⃣ GTIN match
    # ----------------------------------
    normalized_gtin = normalize_gtin(listing.gtin)
    existing_product = None

    if normalized_gtin:
        existing_product = db.query(Product).filter(
            Product.organization_id == organization_id,
            Product.gtin == normalized_gtin,
        ).first()

    # ----------------------------------
    # 2️⃣ Signature match
    # ----------------------------------
    if not existing_product:
        signature = generate_product_signature(
            organization_id=organization_id,
            category_id=category.id,
            subcategory_id=subcategory.id,
            subsubcategory_id=subsubcategory.id,
            product_type_id=product_type.id,
            material_id=material.id,
        )

        existing_product = db.query(Product).filter(
            Product.organization_id == organization_id,
            Product.product_signature == signature,
        ).first()

    # ----------------------------------
    # 3️⃣ Create or reuse product
    # ----------------------------------
    if existing_product:
        product = existing_product

        variant = create_variant_for_existing_product(
            db=db,
            organization_id=organization_id,
            product=product,
            category=product.category,
            subcategory=product.subcategory,
            subsubcategory=product.subsubcategory,
            product_type=product.product_type_rel,
            color=color,
            size=size,
        )
    else:
        product = create_product(
            db=db,
            organization_id=organization_id,
            category=category,
            subcategory=subcategory,
            subsubcategory=subsubcategory,
            product_type=product_type,
            material=material,
            color=color,
            size=size,
            gtin=normalized_gtin,
        )

        variant = product.variants[0]  # created inside create_product

    # ----------------------------------
    # 4️⃣ Link listing
    # ----------------------------------
    listing.product_variant_id = variant.id
    listing.import_status = "LINKED"

    db.commit()

    return {
        "message": "Internal product generated and linked",
        "product_variant_id": variant.id,
        "internal_sku": variant.sku,
    }
