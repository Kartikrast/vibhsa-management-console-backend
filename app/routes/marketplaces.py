import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_context
from app.schemas.marketplace import (
    WalmartConnectRequest,
    AmazonConnectRequest,
    UpdateMarketplaceAccountRequest,
    WalmartReportType,
    WalmartReportRequestCreate,
    WalmartReportRequestResponse,
    WalmartReportRequestsList,
    WalmartRateLimitErrorResponse,
    WalmartItemListingQualityRequest,
)
from app.schemas.marketplace_listing import MarketplaceListingResponse, ImportResponse, MarketplaceInfoResponse
from app.schemas.listing_link import (
    ListingLinkResponse,
    LinkExistingListingRequest,
    GenerateFromListingRequest,
    InventoryUpdateRequest,
    UpdateMarketplaceInventoryRequest,
    MarketplaceInventoryResponse,
    ListingInventoryResponse,
)
from app.models.marketplace_account import MarketplaceAccount
from app.models.marketplace_listing import MarketplaceListing
from app.models.inventory import Inventory
from app.marketplaces.walmart.client import WalmartClient, WalmartRateLimitError
from app.marketplaces.amazon.client import AmazonClient
from app.services.marketplace_import.walmart_import import import_walmart_listings, get_walmart_inventory, sync_listing_content_from_quality, sync_single_listing_quality
from app.services.marketplace_import.amazon_import import import_amazon_listings
from app.services.marketplace_linking_service import link_existing_listing, generate_internal_from_listing
from app.services.inventory_service import update_marketplace_inventory
from app.services.marketplace_reports.walmart_report_service import (
    create_walmart_report_request,
    list_walmart_report_requests,
    get_walmart_report_request,
    refresh_walmart_report_status,
)
from app.models.taxonomy import (
    Category,
    SubCategory,
    SubSubCategory,
    ProductType,
    Material,
    Color,
    Size,
)
from app.services.marketplace_publish.walmart_publish_service import (
    publish_walmart_listing,
)

logger = logging.getLogger(__name__)

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

    expiry = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])

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


@router.patch("/account/{account_id}")
def update_marketplace_account(
    account_id: UUID,
    payload: UpdateMarketplaceAccountRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Update marketplace account settings (e.g. default shipping address)."""
    organization = context["organization"]

    account = (
        db.query(MarketplaceAccount)
        .filter(
            MarketplaceAccount.id == account_id,
            MarketplaceAccount.organization_id == organization.id,
        )
        .first()
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marketplace account not found",
        )

    if payload.default_from_address is not None:
        account.default_from_address = payload.default_from_address.model_dump()

    if payload.default_return_address is not None:
        account.default_return_address = payload.default_return_address.model_dump()

    db.commit()
    db.refresh(account)

    return {
        "id": str(account.id),
        "marketplace": account.marketplace,
        "seller_id": account.seller_id,
        "default_from_address": account.default_from_address,
        "default_return_address": account.default_return_address,
        "message": "Account updated successfully",
    }


@router.post("/amazon/connect")
def connect_amazon(
    payload: AmazonConnectRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    # Prevent duplicate connection
    existing = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "amazon",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amazon already connected",
        )

    # Validate credentials by exchanging refresh_token for access_token
    client = AmazonClient(
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        refresh_token=payload.refresh_token,
        region=payload.region,
    )

    try:
        token_data = client.get_access_token()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Amazon credentials",
        )

    expiry = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])

    account = MarketplaceAccount(
        organization_id=organization.id,
        marketplace="amazon",
        seller_id=payload.seller_id,
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        refresh_token=payload.refresh_token,
        access_token=token_data["access_token"],
        token_expiry=expiry,
        region=payload.region,
        is_active=True,
    )

    db.add(account)
    db.commit()

    return {"message": "Amazon connected successfully"}

@router.get("/amazon/status")
def amazon_connection_status(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "amazon",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        return {"connected": False, "message": "Amazon not connected"}

    return {
        "connected": True,
        "message": "Amazon connected",
        "region": account.region,
    }

@router.post("/amazon/import-listings")
def import_amazon_listings_route(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImportResponse:
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "amazon",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Amazon not connected")

    result = import_amazon_listings(
        db=db,
        organization_id=organization.id,
        marketplace_account=account,
    )

    return result

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

@router.get("/walmart/listing-quality")
def get_walmart_listing_quality(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get seller listing quality score from Walmart."""
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Walmart not connected",
        )

    client = WalmartClient(account)

    try:
        data = client.get_seller_listing_quality(db=db)
    except WalmartRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch listing quality from Walmart: {str(e)}",
        )

    return data

@router.post("/walmart/listing-quality/items")
def get_walmart_item_listing_quality(
    payload: Optional[WalmartItemListingQualityRequest] = None,
    limit: int = 200,
    next_cursor: Optional[str] = None,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get item-level listing quality details from Walmart.

    Returns item quality score, offer score, content score, issues,
    and performance for each item. Supports pagination via limit and nextCursor.
    Optionally, filter by sku or item_id using the request body.
    """
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Walmart not connected",
        )

    # Build the required Walmart payload if sku or item_id is provided
    walmart_payload = None
    if payload:
        if payload.sku:
            walmart_payload = {
                "query": {
                    "field": "sku",
                    "value": payload.sku
                }
            }
        elif payload.item_id:
            walmart_payload = {
                "query": {
                    "field": "itemId",
                    "value": payload.item_id
                }
            }

    client = WalmartClient(account)

    try:
        data = client.get_item_listing_quality_details(
            db=db,
            limit=limit,
            next_cursor=next_cursor,
            payload=walmart_payload,
        )
    except WalmartRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Walmart listing quality items API failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch item listing quality from Walmart: {str(e)}",
        )

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

@router.get("/marketplace-info", response_model=MarketplaceInfoResponse)
def get_marketplace_info(
    listing_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.organization_id == organization.id,
        MarketplaceListing.id == listing_id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Walmart not connected")
    
    inventory_data = get_walmart_inventory(db=db, marketplace_account=account, sku=listing.marketplace_sku)
    data = {
        "marketplace": listing.marketplace,
        "marketplace_sku": listing.marketplace_sku,
        "external_id": listing.external_id,
        "title": listing.marketplace_title,
        "price": listing.price,
        "currency": listing.currency,
        "url": listing.marketplace_url,
        "marketplace_product_type": listing.marketplace_product_type,
        "import_status": listing.import_status,
        "gtin": listing.gtin,
        "listing_status": listing.listing_status,
        "inventory_quantity": inventory_data.get("available_quantity"),
        "images": listing.marketplace_images,
        "customer_rating": listing.marketplace_customer_rating,
        "num_reviews": listing.marketplace_num_reviews,
        "keywords": listing.marketplace_keywords,
    }

    return data

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

    # --------------------------
    # Resolve initial inventory
    # --------------------------
    initial_quantity = 0

    if payload.sync_inventory_from_marketplace:
        listing = db.query(MarketplaceListing).filter(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.organization_id == organization.id,
        ).first()

        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        initial_quantity = _fetch_marketplace_inventory(
            db=db,
            organization_id=organization.id,
            listing=listing,
        )
    elif payload.initial_quantity is not None:
        initial_quantity = payload.initial_quantity

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
        initial_quantity=initial_quantity,
    )


def _fetch_marketplace_inventory(
    db: Session,
    organization_id: UUID,
    listing: MarketplaceListing,
) -> int:
    """Fetch live inventory from the listing's marketplace."""
    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.id == listing.marketplace_account_id,
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Marketplace account not found")

    if listing.marketplace == "walmart":
        inventory_data = get_walmart_inventory(
            db=db,
            marketplace_account=account,
            sku=listing.marketplace_sku,
        )
        return inventory_data.get("available_quantity", 0)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Inventory sync not supported for {listing.marketplace}",
        )


@router.get(
    "/listings/{listing_id}/inventory",
    response_model=ListingInventoryResponse,
)
def get_listing_inventory(
    listing_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get both internal (DB) and marketplace (live API) inventory for a listing."""
    organization = context["organization"]

    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == listing_id,
        MarketplaceListing.organization_id == organization.id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Internal inventory from DB
    internal_available = 0
    internal_reserved = 0

    if listing.product_variant_id:
        inventory = db.query(Inventory).filter(
            Inventory.organization_id == organization.id,
            Inventory.product_variant_id == listing.product_variant_id,
            Inventory.location_name == "default",
        ).first()

        if inventory:
            internal_available = inventory.quantity_available
            internal_reserved = inventory.quantity_reserved

    # Marketplace inventory from live API
    marketplace_quantity = None
    marketplace_source = None
    try:
        marketplace_quantity = _fetch_marketplace_inventory(
            db=db,
            organization_id=organization.id,
            listing=listing,
        )
        marketplace_source = listing.marketplace
    except HTTPException:
        pass  # marketplace inventory unavailable — return None

    return ListingInventoryResponse(
        internal_quantity_available=internal_available,
        internal_quantity_reserved=internal_reserved,
        marketplace_quantity=marketplace_quantity,
        marketplace_source=marketplace_source,
    )


@router.get(
    "/listings/{listing_id}/marketplace-inventory",
    response_model=MarketplaceInventoryResponse,
)
def get_listing_marketplace_inventory(
    listing_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Fetch live inventory from the marketplace for a given listing."""
    organization = context["organization"]

    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == listing_id,
        MarketplaceListing.organization_id == organization.id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    quantity = _fetch_marketplace_inventory(
        db=db,
        organization_id=organization.id,
        listing=listing,
    )

    return MarketplaceInventoryResponse(
        marketplace_quantity=quantity,
        source=listing.marketplace,
    )


@router.patch(
    "/listings/{listing_id}/inventory",
    response_model=MarketplaceInventoryResponse,
)
def update_listing_inventory(
    listing_id: UUID,
    payload: InventoryUpdateRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Manually update inventory for a linked listing's product variant."""
    organization = context["organization"]

    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == listing_id,
        MarketplaceListing.organization_id == organization.id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if not listing.product_variant_id:
        raise HTTPException(
            status_code=400,
            detail="Listing is not linked to any product variant",
        )

    inventory = db.query(Inventory).filter(
        Inventory.organization_id == organization.id,
        Inventory.product_variant_id == listing.product_variant_id,
        Inventory.location_name == "default",
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found")

    inventory.quantity_available = payload.quantity_available
    db.commit()

    return MarketplaceInventoryResponse(
        marketplace_quantity=inventory.quantity_available,
        source=listing.marketplace,
    )

@router.post(
    "/listings/{listing_id}/update-marketplace-inventory",
    response_model=MarketplaceInventoryResponse,
)
def update_marketplace_inventory_route(
    listing_id: UUID,
    payload: UpdateMarketplaceInventoryRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Update inventory on the marketplace for a given listing."""
    organization = context["organization"]

    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == listing_id,
        MarketplaceListing.organization_id == organization.id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if not listing.product_variant_id:
        raise HTTPException(
            status_code=400,
            detail="Listing is not linked to any product variant",
        )

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.id == listing.marketplace_account_id,
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Marketplace account not found")

    # Update marketplace inventory via API
    try:
        update_marketplace_inventory(
            db=db,
            account=account,
            sku=listing.marketplace_sku,
            new_quantity=payload.new_quantity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MarketplaceInventoryResponse(
        marketplace_quantity=payload.new_quantity,
        source=listing.marketplace,
    )

@router.post("/marketplace-listings/{listing_id}/publish")
def publish_listing(
    listing_id: UUID,
    db: Session = Depends(get_db),
):
    return publish_walmart_listing(db, listing_id)


# ========================
# WALMART LISTING QUALITY SYNC
# ========================

@router.get("/listings/{listing_id}/quality")
def get_listing_quality(
    listing_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get stored listing quality data from DB."""
    organization = context["organization"]

    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == listing_id,
        MarketplaceListing.organization_id == organization.id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    return {
        "listing_id": str(listing.id),
        "marketplace_sku": listing.marketplace_sku,
        "quality_score": float(listing.listing_quality_score) if listing.listing_quality_score else None,
        "quality_data": listing.listing_quality_data,
        "marketplace_description": listing.marketplace_description,
        "marketplace_bullet_points": listing.marketplace_bullet_points,
        "has_quality_data": listing.listing_quality_data is not None,
    }


@router.post("/listings/{listing_id}/sync-quality")
def sync_listing_quality(
    listing_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Fetch and store listing quality data for a single listing."""
    organization = context["organization"]

    listing = db.query(MarketplaceListing).filter(
        MarketplaceListing.id == listing_id,
        MarketplaceListing.organization_id == organization.id,
    ).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if not listing.marketplace_sku:
        raise HTTPException(status_code=400, detail="Listing has no marketplace SKU")

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.id == listing.marketplace_account_id,
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Marketplace account not found")

    try:
        result = sync_single_listing_quality(
            db=db,
            listing=listing,
            marketplace_account=account,
        )
        return result
    except WalmartRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Failed to sync quality for listing %s", listing_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync listing quality: {str(e)}",
        )


@router.post("/walmart/sync-listing-content")
def sync_walmart_listing_content(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Sync listing content (description, bullets) from Walmart listing quality data."""
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Walmart not connected",
        )

    try:
        result = sync_listing_content_from_quality(
            db=db,
            organization_id=organization.id,
            marketplace_account=account,
        )
        return result
    except WalmartRateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync listing content from Walmart: {str(e)}",
        )


# ========================
# WALMART REPORTS
# ========================

@router.get("/walmart/report-types", response_model=List[WalmartReportType])
def get_walmart_report_types(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get available Walmart report types and versions."""
    organization = context["organization"]

    # Check if Walmart is connected
    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Walmart not connected",
        )

    client = WalmartClient(account)
    return client.get_available_report_types()


@router.post("/walmart/reports", response_model=WalmartReportRequestResponse)
def create_walmart_report(
    payload: WalmartReportRequestCreate,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Create a new Walmart report request."""
    organization = context["organization"]

    # Check if Walmart is connected
    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Walmart not connected",
        )

    try:
        # Parse datetime strings
        data_start_time = datetime.fromisoformat(payload.data_start_time.replace('Z', '+00:00'))
        data_end_time = datetime.fromisoformat(payload.data_end_time.replace('Z', '+00:00'))

        report_request = create_walmart_report_request(
            db=db,
            organization_id=organization.id,
            marketplace_account_id=account.id,
            report_type=payload.report_type,
            report_version=payload.report_version,
            data_start_time=data_start_time,
            data_end_time=data_end_time,
            row_filters=payload.row_filters,
            exclude_columns=payload.exclude_columns,
        )

        return WalmartReportRequestResponse(
            id=str(report_request.id),
            external_request_id=report_request.external_request_id,
            report_type=report_request.report_type,
            report_version=report_request.report_version,
            data_start_time=report_request.data_start_time.isoformat(),
            data_end_time=report_request.data_end_time.isoformat(),
            status=report_request.status,
            download_url=report_request.download_url,
            expires_at=report_request.expires_at.isoformat() if report_request.expires_at else None,
            completed_at=report_request.completed_at.isoformat() if report_request.completed_at else None,
            failed_at=report_request.failed_at.isoformat() if report_request.failed_at else None,
            error=report_request.error,
            created_at=report_request.created_at.isoformat(),
            updated_at=report_request.updated_at.isoformat(),
        )
    except WalmartRateLimitError as e:
        # Calculate retry_after_seconds if possible
        retry_after = None
        if e.next_replenishment_time:
            now = datetime.now(timezone.utc)
            if e.next_replenishment_time > now:
                retry_after = int((e.next_replenishment_time - now).total_seconds())

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=WalmartRateLimitErrorResponse(
                remaining_tokens=e.remaining_tokens,
                max_tokens=e.max_tokens,
                next_replenishment_time=e.next_replenishment_time.isoformat() if e.next_replenishment_time else None,
                retry_after_seconds=retry_after,
            ).model_dump(),
        )
    except Exception as e:
        logger.exception("Failed to create Walmart report")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create Walmart report: {str(e)}",
        )


@router.get("/walmart/reports", response_model=WalmartReportRequestsList)
def list_walmart_reports(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """List Walmart report requests."""
    organization = context["organization"]

    # Check if Walmart is connected
    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Walmart not connected",
        )

    reports = list_walmart_report_requests(
        db=db,
        organization_id=organization.id,
        marketplace_account_id=account.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    # Convert to response format
    report_responses = []
    for report in reports:
        report_responses.append(WalmartReportRequestResponse(
            id=str(report.id),
            external_request_id=report.external_request_id,
            report_type=report.report_type,
            report_version=report.report_version,
            data_start_time=report.data_start_time.isoformat(),
            data_end_time=report.data_end_time.isoformat(),
            status=report.status,
            download_url=report.download_url,
            expires_at=report.expires_at.isoformat() if report.expires_at else None,
            completed_at=report.completed_at.isoformat() if report.completed_at else None,
            failed_at=report.failed_at.isoformat() if report.failed_at else None,
            error=report.error,
            created_at=report.created_at.isoformat(),
            updated_at=report.updated_at.isoformat(),
        ))

    return WalmartReportRequestsList(
        reports=report_responses,
        total=len(report_responses),  # For simplicity, could be improved with count query
    )


@router.get("/walmart/reports/{report_id}", response_model=WalmartReportRequestResponse)
def get_walmart_report(
    report_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get a specific Walmart report request."""
    organization = context["organization"]

    try:
        report_request = get_walmart_report_request(
            db=db,
            organization_id=organization.id,
            report_request_id=report_id,
        )

        return WalmartReportRequestResponse(
            id=str(report_request.id),
            external_request_id=report_request.external_request_id,
            report_type=report_request.report_type,
            report_version=report_request.report_version,
            data_start_time=report_request.data_start_time.isoformat(),
            data_end_time=report_request.data_end_time.isoformat(),
            status=report_request.status,
            download_url=report_request.download_url,
            expires_at=report_request.expires_at.isoformat() if report_request.expires_at else None,
            completed_at=report_request.completed_at.isoformat() if report_request.completed_at else None,
            failed_at=report_request.failed_at.isoformat() if report_request.failed_at else None,
            error=report_request.error,
            created_at=report_request.created_at.isoformat(),
            updated_at=report_request.updated_at.isoformat(),
        )
    except WalmartRateLimitError as e:
        retry_after = None
        if e.next_replenishment_time:
            now = datetime.now(timezone.utc)
            if e.next_replenishment_time > now:
                retry_after = int((e.next_replenishment_time - now).total_seconds())

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=WalmartRateLimitErrorResponse(
                remaining_tokens=e.remaining_tokens,
                max_tokens=e.max_tokens,
                next_replenishment_time=e.next_replenishment_time.isoformat() if e.next_replenishment_time else None,
                retry_after_seconds=retry_after,
            ).model_dump(),
        )


@router.post("/walmart/reports/{report_id}/refresh")
def refresh_walmart_report_status(
    report_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Refresh the status of a Walmart report request."""
    organization = context["organization"]

    try:
        report_request = refresh_walmart_report_status(
            db=db,
            organization_id=organization.id,
            report_request_id=report_id,
        )

        return {
            "message": "Report status refreshed",
            "status": report_request.status,
            "download_url": report_request.download_url,
        }
    except WalmartRateLimitError as e:
        retry_after = None
        if e.next_replenishment_time:
            now = datetime.now(timezone.utc)
            if e.next_replenishment_time > now:
                retry_after = int((e.next_replenishment_time - now).total_seconds())

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=WalmartRateLimitErrorResponse(
                remaining_tokens=e.remaining_tokens,
                max_tokens=e.max_tokens,
                next_replenishment_time=e.next_replenishment_time.isoformat() if e.next_replenishment_time else None,
                retry_after_seconds=retry_after,
            ).model_dump(),
        )