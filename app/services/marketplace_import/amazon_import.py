import logging
from sqlalchemy.orm import Session
from app.models.marketplace_listing import MarketplaceListing
from app.marketplaces.amazon.client import AmazonClient
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


def import_amazon_listings(
    db: Session,
    organization_id,
    marketplace_account,
):
    """
    Import listings from Amazon via the Reports API (GET_MERCHANT_LISTINGS_ALL_DATA).

    The report returns TSV rows with columns like:
        item-name, item-description, listing-id, seller-sku, price, quantity,
        open-date, image-url, item-is-marketplace, product-id-type,
        item-condition, asin1, product-id, fulfillment-channel, status, ...

    We map these into our MarketplaceListing model.
    """
    client = AmazonClient(marketplace_account)

    items = client.get_listings(db=db)

    imported_count = 0
    updated_count = 0
    skipped_count = 0

    for item in items:
        # --------------------------------------------------
        # Extract fields from the TSV row
        # --------------------------------------------------
        asin = (item.get("asin1") or "").strip()
        sku = (item.get("seller-sku") or "").strip()
        title = (item.get("item-name") or "").strip()
        listing_id = (item.get("listing-id") or "").strip()

        # Use ASIN as the external_id — it's Amazon's unique product identifier
        external_id = asin
        if not external_id:
            logger.warning("Skipping Amazon listing with no ASIN: sku=%s", sku)
            skipped_count += 1
            continue

        # Price
        raw_price = (item.get("price") or "").strip()
        try:
            price = Decimal(raw_price) if raw_price else None
        except (InvalidOperation, ValueError):
            price = None

        currency = "USD"

        # GTIN / product-id
        product_id = (item.get("product-id") or "").strip()
        product_id_type = (item.get("product-id-type") or "").strip()

        # Only treat product-id as a GTIN if the type indicates UPC/EAN/ISBN
        gtin = None
        if product_id_type in ("1", "2", "3", "4", "UPC", "EAN", "ISBN", "GTIN"):
            gtin = product_id

        # Listing status from Amazon report
        listing_status = (item.get("status") or "Active").strip()

        # --------------------------------------------------
        # Upsert into MarketplaceListing
        # --------------------------------------------------
        existing = db.query(MarketplaceListing).filter(
            MarketplaceListing.organization_id == organization_id,
            MarketplaceListing.marketplace == "amazon",
            MarketplaceListing.external_id == external_id,
        ).first()

        if existing:
            existing.marketplace_title = title
            existing.marketplace_sku = sku
            existing.price = price
            existing.currency = currency
            existing.gtin = gtin
            existing.listing_status = listing_status
            existing.raw_payload = item
            existing.last_synced_at = datetime.now(timezone.utc)
            updated_count += 1
        else:
            listing = MarketplaceListing(
                organization_id=organization_id,
                marketplace_account_id=marketplace_account.id,
                marketplace="amazon",
                external_id=external_id,
                marketplace_sku=sku,
                marketplace_title=title,
                price=price,
                currency=currency,
                gtin=gtin,
                listing_status=listing_status,
                import_status="UNLINKED",
                raw_payload=item,
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(listing)
            imported_count += 1

    db.commit()

    logger.info(
        "Amazon import complete: imported=%d, updated=%d, skipped=%d",
        imported_count, updated_count, skipped_count,
    )

    return {
        "imported": imported_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "message": "Import completed",
    }
