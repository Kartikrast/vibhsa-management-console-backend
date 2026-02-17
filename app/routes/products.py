from fastapi import APIRouter, Depends, HTTPException, status
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
)

from app.models.taxonomy import Category, SubCategory, SubSubCategory, ProductType, Material, Color, Size
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.inventory import Inventory

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
            joinedload(Product.product_type),
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

    # 🔒 Update only provided fields
    update_data = payload.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return product
