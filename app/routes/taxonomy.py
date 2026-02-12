from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

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
    return db.query(Category).filter(Category.is_active.is_(True)).all()


# ========================
# SubCategories
# ========================
@router.get("/subcategories", response_model=list[SimpleTaxonomyResponse])
def get_subcategories(
    category_id: str = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(SubCategory)
        .filter(
            SubCategory.category_id == category_id,
            SubCategory.is_active.is_(True),
        )
        .all()
    )


# ========================
# SubSubCategories
# ========================
@router.get("/subsubcategories", response_model=list[SimpleTaxonomyResponse])
def get_subsubcategories(
    subcategory_id: str = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(SubSubCategory)
        .filter(
            SubSubCategory.subcategory_id == subcategory_id,
            SubSubCategory.is_active.is_(True),
        )
        .all()
    )


# ========================
# Product Types
# ========================
@router.get("/product-types", response_model=list[SimpleTaxonomyResponse])
def get_product_types(db: Session = Depends(get_db)):
    return db.query(ProductType).filter(ProductType.is_active.is_(True)).all()


# ========================
# Materials
# ========================
@router.get("/materials", response_model=list[SimpleTaxonomyResponse])
def get_materials(db: Session = Depends(get_db)):
    return db.query(Material).filter(Material.is_active.is_(True)).all()


# ========================
# Colors
# ========================
@router.get("/colors", response_model=list[SimpleTaxonomyResponse])
def get_colors(db: Session = Depends(get_db)):
    return db.query(Color).filter(Color.is_active.is_(True)).all()


# ========================
# Sizes
# ========================
@router.get("/sizes", response_model=list[SimpleTaxonomyResponse])
def get_sizes(db: Session = Depends(get_db)):
    return db.query(Size).filter(Size.is_active.is_(True)).all()
