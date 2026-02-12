from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_context

from app.schemas.product import ProductCreateRequest, ProductResponse, ProductListResponse, VariantResponse

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

@router.get("", response_model=list[ProductListResponse])
def get_products(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    organization = context["organization"]

    products = (
        db.query(Product)
        .options(
            joinedload(Product.variants)
            .joinedload(ProductVariant.color),
            joinedload(Product.variants)
            .joinedload(ProductVariant.size),
            joinedload(Product.category),
            joinedload(Product.product_type),
            joinedload(Product.material),
        )
        .filter(Product.organization_id == organization.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    result = []

    for product in products:
        variant_list = []

        for variant in product.variants:
            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.product_variant_id == variant.id,
                    Inventory.organization_id == organization.id,
                )
                .first()
            )

            variant_list.append(
                VariantResponse(
                    id=variant.id,
                    sku=variant.sku,
                    color=variant.color.name if variant.color else None,
                    size=variant.size.name if variant.size else None,
                    quantity_available=inventory.quantity_available if inventory else 0,
                )
            )

        result.append(
            ProductListResponse(
                id=product.id,
                product_code=product.product_code,
                category=product.category.name,
                product_type=product.product_type.name,
                material=product.material.name,
                created_at=product.created_at,
                variants=variant_list,
            )
        )

    return result