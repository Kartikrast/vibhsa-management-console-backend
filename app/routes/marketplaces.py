from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_context
from app.schemas.marketplace import WalmartConnectRequest
from app.schemas.marketplace_listing import MarketplaceListingResponse, ImportResponse
from app.schemas.listing_link import ListingLinkResponse, LinkExistingListingRequest, GenerateFromListingRequest
from app.models.marketplace_account import MarketplaceAccount
from app.models.marketplace_listing import MarketplaceListing
from app.marketplaces.walmart.client import WalmartClient
from app.services.marketplace_import.walmart_import import import_walmart_listings
from app.services.marketplace_linking_service import link_existing_listing, generate_internal_from_listing
from app.models.taxonomy import (
    Category,
    SubCategory,
    SubSubCategory,
    ProductType,
    Material,
    Color,
    Size,
)

router = APIRouter(prefix="/marketplaces", tags=["Marketplaces"])

@router.post("/walmart/connect")
def connect_walmart(
    payload: WalmartConnectRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    # Prevent duplicate connection
    existing = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Walmart already connected",
        )

    # Create client
    client = WalmartClient(
        client_id=payload.client_id,
        client_secret=payload.client_secret,
    )

    try:
        token_data = client.get_access_token()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Walmart credentials",
        )

    expiry = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])

    account = MarketplaceAccount(
        organization_id=organization.id,
        marketplace="walmart",
        seller_id=payload.seller_id,
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        access_token=token_data["access_token"],
        token_expiry=expiry,
        is_active=True,
    )

    db.add(account)
    db.commit()

    return {"message": "Walmart connected successfully"}

@router.get("/walmart/items")
def fetch_walmart_items(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Walmart not connected",
        )

    client = WalmartClient(account)

    data = client.get_items(db=db, limit=10)

    return data

@router.get("/walmart/status")
def walmart_connection_status(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        return {"connected": False, "message": "Walmart not connected"}

    return {
        "connected": True,
        "message": "Walmart connected"
    }

@router.post("/walmart/import-listings")
def import_walmart_listings_route(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImportResponse:
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Walmart not connected")

    result = import_walmart_listings(
        db=db,
        organization_id=organization.id,
        marketplace_account=account,
    )

    return result

@router.get("/listings", response_model=list[MarketplaceListingResponse])
def get_marketplace_listings(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    query = db.query(MarketplaceListing).filter(
        MarketplaceListing.organization_id == organization.id
    )

    if status:
        query = query.filter(MarketplaceListing.import_status == status)

    listings = (
        query
        .order_by(MarketplaceListing.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return listings

@router.post(
    "/listings/{listing_id}/link-existing",
    response_model=ListingLinkResponse,
)
def link_existing(
    listing_id: UUID,
    payload: LinkExistingListingRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    return link_existing_listing(
        db=db,
        organization_id=organization.id,
        listing_id=listing_id,
        product_variant_id=payload.product_variant_id,
    )



@router.post(
    "/listings/{listing_id}/generate-internal",
    response_model=ListingLinkResponse,
)
def generate_internal(
    listing_id: UUID,
    payload: GenerateFromListingRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    # --------------------------
    # Fetch taxonomy models
    # --------------------------
    category = db.get(Category, payload.category_id)
    subcategory = db.get(SubCategory, payload.subcategory_id)
    subsubcategory = db.get(SubSubCategory, payload.subsubcategory_id)
    product_type = db.get(ProductType, payload.product_type_id)
    material = db.get(Material, payload.material_id)
    color = db.get(Color, payload.color_id)
    size = db.get(Size, payload.size_id)

    if not all([category, subcategory, product_type, material]):
        raise HTTPException(status_code=400, detail="Invalid taxonomy selection")

    return generate_internal_from_listing(
        db=db,
        organization_id=organization.id,
        listing_id=listing_id,
        category=category,
        subcategory=subcategory,
        subsubcategory=subsubcategory,
        product_type=product_type,
        material=material,
        color=color,
        size=size,
    )