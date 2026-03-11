from sqlalchemy.orm import Session

from app.models.marketplace_listing import MarketplaceListing
from app.marketplaces.walmart.client import WalmartClient

def process_walmart_feed_status(
    db: Session,
    listing: MarketplaceListing,
    walmart_client: WalmartClient,
):
    """
    Check feed status and update marketplace listing state.
    """

    if not listing.last_feed_id:
        return

    feed = walmart_client.get_feed_status(db, listing.last_feed_id)

    feed_status = feed.get("feedStatus")

    listing.last_feed_status = feed_status

    # Feed still processing
    if feed_status in ["RECEIVED", "INPROGRESS"]:
        listing.sync_status = "processing"
        db.commit()
        return

    # Feed failed before ingestion
    if feed_status == "ERROR":

        errors = feed.get("ingestionErrors", {}).get("ingestionError", [])

        if errors:
            listing.last_feed_error = errors[0].get("description")

        listing.sync_status = "error"
        db.commit()
        return

    # Feed processed successfully → check item status
    if feed_status == "PROCESSED":

        item_status = walmart_client.get_feed_item_status(db=db, feed_id=listing.last_feed_id)

        results = item_status.get("itemDetails", {}).get("itemIngestionStatus", [])

        if not results:
            listing.sync_status = "synced"
            listing.listing_status = "published"
            db.commit()
            return

        item = results[0]

        if item.get("ingestionStatus") == "SUCCESS":

            listing.sync_status = "synced"
            listing.listing_status = "published"
            listing.last_feed_error = None

        else:

            errors = item.get("errors", [])

            if errors:
                listing.last_feed_error = errors[0].get("description")

            listing.sync_status = "failed"

        db.commit()