import re
from sqlalchemy.orm import Session
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.models.google_taxonomy import GoogleTaxonomy
from app.models.taxonomy import (
    Category,
    SubCategory,
    SubSubCategory,
    ProductType,
)

# ======================================================
# SHORT CODE GENERATOR
# ======================================================

def normalize_name(name: str) -> str:
    name = name.upper()
    name = re.sub(r"[^A-Z0-9]", "", name)
    return name


def generate_unique_short_code(
    db: Session,
    model,
    parent_field_name: str | None,
    parent_id,
    name: str,
    max_length: int = 10,
):
    base = normalize_name(name)[:max_length]
    short_code = base
    counter = 1

    while True:
        query = db.query(model).filter(model.short_code == short_code)

        if parent_field_name and parent_id:
            query = query.filter(
                getattr(model, parent_field_name) == parent_id
            )

        existing = query.first()

        if not existing:
            return short_code

        trimmed_base = base[: max_length - len(str(counter))]
        short_code = f"{trimmed_base}{counter}"
        counter += 1


# ======================================================
# GET OR CREATE HELPERS
# ======================================================

def get_or_create_category(db: Session, name: str):
    existing = db.query(Category).filter(Category.name == name).first()
    if existing:
        return existing

    short_code = generate_unique_short_code(
        db, Category, None, None, name, 10
    )

    obj = Category(name=name, short_code=short_code)
    db.add(obj)
    db.flush()
    return obj


def get_or_create_subcategory(db: Session, category, name: str):
    existing = (
        db.query(SubCategory)
        .filter(
            SubCategory.category_id == category.id,
            SubCategory.name == name,
        )
        .first()
    )

    if existing:
        return existing

    short_code = generate_unique_short_code(
        db, SubCategory, "category_id", category.id, name, 10
    )

    obj = SubCategory(
        category_id=category.id,
        name=name,
        short_code=short_code,
    )

    db.add(obj)
    db.flush()
    return obj


def get_or_create_subsubcategory(db: Session, subcategory, name: str):
    existing = (
        db.query(SubSubCategory)
        .filter(
            SubSubCategory.subcategory_id == subcategory.id,
            SubSubCategory.name == name,
        )
        .first()
    )

    if existing:
        return existing

    short_code = generate_unique_short_code(
        db, SubSubCategory, "subcategory_id", subcategory.id, name, 10
    )

    obj = SubSubCategory(
        subcategory_id=subcategory.id,
        name=name,
        short_code=short_code,
    )

    db.add(obj)
    db.flush()
    return obj


def get_or_create_product_type(db: Session, subsubcategory, name: str):
    existing = (
        db.query(ProductType)
        .filter(
            ProductType.subsubcategory_id == subsubcategory.id,
            ProductType.name == name,
        )
        .first()
    )

    if existing:
        return existing

    short_code = generate_unique_short_code(
        db,
        ProductType,
        "subsubcategory_id",
        subsubcategory.id,
        name,
        20,
    )

    obj = ProductType(
        subsubcategory_id=subsubcategory.id,
        name=name,
        short_code=short_code,
    )

    db.add(obj)
    db.flush()
    return obj


# ======================================================
# FLATTEN ENGINE
# ======================================================

def flatten_google_taxonomy():
    db: Session = SessionLocal()

    try:
        leaf_nodes = (
            db.query(GoogleTaxonomy)
            .filter(GoogleTaxonomy.is_leaf.is_(True))
            .all()
        )

        print(f"Found {len(leaf_nodes)} leaf nodes")

        for node in leaf_nodes:
            parts = [p.strip() for p in node.full_path.split(">")]

            if not parts:
                continue

            category_name = parts[0]
            subcategory_name = parts[1] if len(parts) > 1 else None
            subsubcategory_name = parts[2] if len(parts) > 2 else None

            # product type is always last node
            product_type_name = parts[-1]

            category = get_or_create_category(db, category_name)

            subcategory = None
            if subcategory_name:
                subcategory = get_or_create_subcategory(
                    db, category, subcategory_name
                )

            subsubcategory = None
            if subsubcategory_name and subcategory:
                subsubcategory = get_or_create_subsubcategory(
                    db, subcategory, subsubcategory_name
                )

            # ONLY create product type if subsubcategory exists
            if subsubcategory:
                get_or_create_product_type(
                    db, subsubcategory, product_type_name
                )

        db.commit()
        print("===================================")
        print("✅ Flattening Complete")
        print("===================================")

    except Exception as e:
        db.rollback()
        print("❌ Error:", str(e))

    finally:
        db.close()


if __name__ == "__main__":
    flatten_google_taxonomy()
