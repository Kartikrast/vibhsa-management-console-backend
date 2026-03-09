from sqlalchemy.orm import Session
from app.models.marketplace_listing import MarketplaceListing
from app.marketplaces.walmart.client import WalmartClient
from decimal import Decimal
from datetime import datetime, timezone


def import_walmart_listings(
    db: Session,
    organization_id,
    marketplace_account,
):
    client = WalmartClient(marketplace_account)

    response = client.get_items(db=db, limit=50)

    items = response.get("ItemResponse", [])

    imported_count = 0
    updated_count = 0

    for item in items:

        external_id = item.get("wpid")
        sku = item.get("sku")
        title = item.get("productName")
        product_type = item.get("productType")

        price_data = item.get("price") or {}
        price = price_data.get("amount")
        currency = price_data.get("currency", "USD")
        gtin = item.get("gtin") or item.get("upc")

        listing_status = item.get("lifecycleStatus", "UNKNOWN")

        if not external_id:
            continue

        existing = db.query(MarketplaceListing).filter(
            MarketplaceListing.organization_id == organization_id,
            MarketplaceListing.marketplace == "walmart",
            MarketplaceListing.external_id == external_id,
        ).first()

        if existing:
            existing.title = title
            existing.marketplace_sku = sku
            existing.price = Decimal(price) if price else None
            existing.currency = currency
            existing.gtin = gtin
            existing.listing_status = listing_status
            existing.raw_payload = item
            existing.product_type = product_type
            existing.updated_at = datetime.now(timezone.utc)
            updated_count += 1

        else:
            listing = MarketplaceListing(
                organization_id=organization_id,
                marketplace_account_id=marketplace_account.id,
                marketplace="walmart",
                external_id=external_id,
                marketplace_sku=sku,
                title=title,
                price=Decimal(price) if price else None,
                currency=currency,
                gtin=gtin,
                listing_status=listing_status,
                import_status="UNLINKED",
                raw_payload=item,
                product_type=product_type,
            )

            db.add(listing)
            imported_count += 1

    db.commit()

    return {
        "imported": imported_count,
        "updated": updated_count,
        "skipped": len(items) - imported_count - updated_count,
        "message": "Import completed",
    }
