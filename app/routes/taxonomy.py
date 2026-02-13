from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.schemas.taxonomy import SimpleTaxonomyResponse

from app.models.taxonomy import (
    Category,
    SubCategory,
    SubSubCategory,
    ProductType,
    Material,
    Color,
    Size,
)

router = APIRouter(prefix="/taxonomy", tags=["Taxonomy"])


# ========================
# Categories
# ========================
@router.get("/categories", response_model=list[SimpleTaxonomyResponse])
def get_categories(db: Session = Depends(get_db)):
    return (
        db.query(Category)
        .filter(Category.is_active.is_(True))
        .order_by(Category.name.asc())
        .all()
    )


# ========================
# SubCategories
# ========================
@router.get("/subcategories", response_model=list[SimpleTaxonomyResponse])
def get_subcategories(
    category_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(SubCategory)
        .filter(
            SubCategory.category_id == category_id,
            SubCategory.is_active.is_(True),
        )
        .order_by(SubCategory.name.asc())
        .all()
    )


# ========================
# SubSubCategories
# ========================
@router.get("/subsubcategories", response_model=list[SimpleTaxonomyResponse])
def get_subsubcategories(
    subcategory_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(SubSubCategory)
        .filter(
            SubSubCategory.subcategory_id == subcategory_id,
            SubSubCategory.is_active.is_(True),
        )
        .order_by(SubSubCategory.name.asc())
        .all()
    )


# ========================
# Product Types (FIXED)
# ========================
@router.get("/product-types", response_model=list[SimpleTaxonomyResponse])
def get_product_types(
    subsubcategory_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(ProductType)
        .filter(
            ProductType.subsubcategory_id == subsubcategory_id,
            ProductType.is_active.is_(True),
        )
        .order_by(ProductType.name.asc())
        .all()
    )


# ========================
# Materials
# ========================
@router.get("/materials", response_model=list[SimpleTaxonomyResponse])
def get_materials(db: Session = Depends(get_db)):
    return (
        db.query(Material)
        .filter(Material.is_active.is_(True))
        .order_by(Material.name.asc())
        .all()
    )


# ========================
# Colors
# ========================
@router.get("/colors", response_model=list[SimpleTaxonomyResponse])
def get_colors(db: Session = Depends(get_db)):
    return (
        db.query(Color)
        .filter(Color.is_active.is_(True))
        .order_by(Color.name.asc())
        .all()
    )


# ========================
# Sizes
# ========================
@router.get("/sizes", response_model=list[SimpleTaxonomyResponse])
def get_sizes(db: Session = Depends(get_db)):
    return (
        db.query(Size)
        .filter(Size.is_active.is_(True))
        .order_by(Size.name.asc())
        .all()
    )

