from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.marketplace_listing import MarketplaceListing
from app.marketplaces.walmart.client import WalmartClient
from app.services.marketplace_publish.walmart_feed_builder import (
    build_walmart_item_feed,
)


def publish_walmart_listing(db: Session, listing_id):

    listing = (
        db.query(MarketplaceListing)
        .filter(MarketplaceListing.id == listing_id)
        .first()
    )

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.marketplace != "walmart":
        raise HTTPException(
            status_code=400,
            detail="Listing is not a Walmart listing",
        )

    if not listing.product_variant:
        raise HTTPException(
            status_code=400,
            detail="Listing is not linked to a product variant",
        )

    variant = listing.product_variant
    product = variant.product
    account = listing.marketplace_account

    client = WalmartClient(account)

    payload = build_walmart_item_feed(
        product=product,
        variant=variant,
        listing=listing,
    )

    feed_type = "MP_MAINTENANCE" if listing.external_id else "MP_ITEM"

    response = client.submit_feed(
        db=db,
        feed_type=feed_type,
        payload=payload,
    )

    listing.last_feed_id = response.get("feedId")
    listing.sync_status = "processing"
    listing.last_feed_status = "RECEIVED"

    db.commit()

    return {
        "message": "Feed submitted successfully",
        "feed_id": listing.last_feed_id,
    }