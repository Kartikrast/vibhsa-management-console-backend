from sqlalchemy.orm import Session
from app.core.database import SessionLocal

from app.models.marketplace_listing import MarketplaceListing
from app.marketplaces.walmart.client import WalmartClient
from app.services.marketplace_publish.walmart_feed_status_service import process_walmart_feed_status



def sync_walmart_feed_status():

    db: Session = SessionLocal()

    listings = (
        db.query(MarketplaceListing)
        .filter(
            MarketplaceListing.marketplace == "walmart",
            MarketplaceListing.sync_status == "processing",
            MarketplaceListing.last_feed_id.isnot(None),
        )
        .all()
    )

    for listing in listings:
        try:
            client = WalmartClient(listing.marketplace_account)
            process_walmart_feed_status(
                db=db,
                listing=listing,
                walmart_client=client,
            )
        except Exception as e:
            listing.sync_status = "failed"
            listing.last_feed_error = str(e)

            db.commit()
    db.close()