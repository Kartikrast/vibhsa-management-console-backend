import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_context

from app.schemas.product import ProductCreateRequest, ProductResponse, ProductListResponse, PaginatedProductListResponse
from app.schemas.product_display import (
    ProductListItemResponse,
    ProductDetailResponse,
    UpdateProductRequest,
    ReorderMediaRequest,
    ProductMediaResponse,
)

from app.models.taxonomy import Category, SubCategory, SubSubCategory, ProductType, Material, Color, Size
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory
from app.models.product_media import ProductMedia

from app.services.product_service import create_product

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductResponse)
def create_product_endpoint(
    payload: ProductCreateRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    # ------------------------------
    # Validate Taxonomy
    # ------------------------------
    category = db.get(Category, payload.category_id)
    subcategory = db.get(SubCategory, payload.subcategory_id)
    subsubcategory = (
        db.get(SubSubCategory, payload.subsubcategory_id)
        if payload.subsubcategory_id
        else None
    )
    product_type = db.get(ProductType, payload.product_type_id)
    material = db.get(Material, payload.material_id)
    color = db.get(Color, payload.color_id) if payload.color_id else None
    size = db.get(Size, payload.size_id) if payload.size_id else None

    if not all([category, subcategory, product_type, material]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid taxonomy selection",
        )

    try:
        product = create_product(
            db=db,
            organization_id=organization.id,
            category=category,
            subcategory=subcategory,
            subsubcategory=subsubcategory,
            product_type=product_type,
            material=material,
            color=color,
            size=size,
        )

        return product

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.get("", response_model=PaginatedProductListResponse)
def get_products(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
    page: int = 1,
    limit: int = 20,
):
    organization = context["organization"]

    query = db.query(Product).filter(
        Product.organization_id == organization.id
    )

    total = query.count()

    products = (
        query.order_by(Product.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = [
        ProductListItemResponse.model_validate(product)
        for product in products
    ]

    return PaginatedProductListResponse(
        data=data,
        total=total,
        page=page,
        limit=limit,
    )

@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product_detail(
    product_id: str,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    product = (
        db.query(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.subcategory),
            joinedload(Product.subsubcategory),
            joinedload(Product.product_type_rel),
            joinedload(Product.material),
            joinedload(Product.variants)
            .joinedload(ProductVariant.color),
            joinedload(Product.variants)
            .joinedload(ProductVariant.size),
            joinedload(Product.variants)
            .joinedload(ProductVariant.media),
            joinedload(Product.variants)
            .joinedload(ProductVariant.marketplace_listings),
        )
        .filter(
            Product.id == product_id,
            Product.organization_id == organization.id,
        )
        .first()
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return ProductDetailResponse.model_validate(product)

@router.patch("/{product_id}", response_model=ProductDetailResponse)
def update_product(
    product_id: UUID,
    payload: UpdateProductRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    product = (
        db.query(Product)
        .filter(
            Product.id == product_id,
            Product.organization_id == organization.id,
        )
        .first()
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if payload.gtin:
        existing = db.query(Product).filter(
            Product.organization_id == organization.id,
            Product.gtin == payload.gtin,
            Product.id != product.id
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="GTIN already exists for another product"
            )


    # 🔒 Update only provided fields
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return ProductDetailResponse.model_validate(product)


@router.post("/variants/{variant_id}/media")
def upload_variant_media(
    variant_id: UUID,
    file: UploadFile = File(...),
    media_type: str = "image",
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    variant = (
        db.query(ProductVariant)
        .filter(
            ProductVariant.id == variant_id,
            ProductVariant.organization_id == organization.id,
        )
        .first()
    )

    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    if media_type not in ["image", "video"]:
        raise HTTPException(status_code=400, detail="Invalid media type")

    # ----------------------------------
    # Create Folder Based on SKU
    # ----------------------------------
    sku = variant.sku
    variant_folder = Path(f"media/variants/{sku}")
    variant_folder.mkdir(parents=True, exist_ok=True)

    # Determine next index
    existing_media_count = (
        db.query(ProductMedia)
        .filter(
            ProductMedia.product_variant_id == variant.id,
            ProductMedia.organization_id == organization.id,
            ProductMedia.media_type == media_type,
        )
        .count()
    )

    next_index = existing_media_count + 1

    # Generate File Name
    file_ext = file.filename.split(".")[-1].lower()

    if media_type == "image":
        file_name = f"{sku}_I{next_index}.{file_ext}"
    else:
        file_name = f"{sku}_V{next_index}.{file_ext}"

    file_path = variant_folder / file_name

    # Save File
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    media_url = f"/media/variants/{sku}/{file_name}"

    # Save DB Record
    media = ProductMedia(
        organization_id=organization.id,
        product_variant_id=variant.id,
        media_type=media_type,
        media_url=media_url,
        display_order=next_index,
        is_primary=(next_index == 1 and media_type == "image"),
    )

    db.add(media)
    db.commit()

    return {
        "message": "Media uploaded successfully",
        "media_url": media_url,
    }

@router.get("/variants/{variant_id}/media", response_model=list[ProductMediaResponse])
def get_variant_media(
    variant_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    media = (
        db.query(ProductMedia)
        .filter(
            ProductMedia.product_variant_id == variant_id,
            ProductMedia.organization_id == organization.id,
        )
        .order_by(ProductMedia.display_order.asc())
        .all()
    )

    return [ProductMediaResponse.model_validate(m) for m in media]

@router.delete("/variants/{variant_id}/media/{media_id}")
def delete_media(
    variant_id: UUID,
    media_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    media = db.query(ProductMedia).filter(
        ProductMedia.id == media_id,
        ProductMedia.product_variant_id == variant_id,
        ProductMedia.organization_id == organization.id,
    ).first()

    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    # Delete file from disk
    media_base_dir = Path("media").resolve()
    media_rel_path = Path(str(media.media_url).lstrip("/"))
    file_path = (Path(".") / media_rel_path).resolve()

    if media_base_dir in file_path.parents and file_path.is_file():
        try:
            file_path.unlink()
        except OSError:
            pass

    was_primary = media.is_primary
    deleted_media_type = media.media_type

    db.delete(media)
    db.flush()

    # Reorder remaining media
    remaining = (
        db.query(ProductMedia)
        .filter(
            ProductMedia.product_variant_id == variant_id,
            ProductMedia.organization_id == organization.id,
            ProductMedia.media_type == deleted_media_type,
        )
        .order_by(ProductMedia.display_order.asc())
        .all()
    )

    for index, item in enumerate(remaining, start=1):
        item.display_order = index

    # If primary deleted → set first image as primary
    if deleted_media_type == "image":
        if was_primary and remaining:
            remaining[0].is_primary = True

    db.commit()

    return {"message": "Media deleted successfully"}

@router.post("/variants/{variant_id}/media/{media_id}/set-primary")
def set_primary_media(
    variant_id: UUID,
    media_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    media = db.query(ProductMedia).filter(
        ProductMedia.id == media_id,
        ProductMedia.product_variant_id == variant_id,
        ProductMedia.organization_id == organization.id,
    ).first()

    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    
    if media.media_type != "image":
        raise HTTPException(status_code=400, detail="Only images can be set as primary")

    # Reset all to False
    db.query(ProductMedia).filter(
        ProductMedia.product_variant_id == variant_id,
        ProductMedia.organization_id == organization.id,
        ProductMedia.media_type == "image",
    ).update({"is_primary": False})

    media.is_primary = True

    db.commit()

    return {"message": "Primary image updated"}

@router.post("/variants/{variant_id}/media/reorder")
def reorder_media(
    variant_id: UUID,
    payload: ReorderMediaRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    media_list = db.query(ProductMedia).filter(
        ProductMedia.product_variant_id == variant_id,
        ProductMedia.organization_id == organization.id,
    ).all()

    media_map = {m.id: m for m in media_list}

    if set(payload.ordered_media_ids) != set(media_map.keys()):
        raise HTTPException(status_code=400, detail="Invalid media ordering")

    for index, media_id in enumerate(payload.ordered_media_ids, start=1):
        media_map[media_id].display_order = index

    db.commit()

    return {"message": "Media reordered successfully"}