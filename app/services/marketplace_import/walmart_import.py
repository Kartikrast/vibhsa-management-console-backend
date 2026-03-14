from sqlalchemy.orm import Session
from app.models.marketplace_listing import MarketplaceListing
from app.marketplaces.walmart.client import WalmartClient
from decimal import Decimal
from datetime import datetime, timezone


def generate_walmart_item_url(item_id):
    return f"https://www.walmart.com/ip/{item_id}"


def import_walmart_listings(
    db: Session,
    organization_id,
    marketplace_account,
):
    client = WalmartClient(marketplace_account)

    imported_count = 0
    updated_count = 0
    total_fetched = 0
    next_cursor = "*"

    while True:
        response = client.get_items(db=db, limit=50, next_cursor=next_cursor)
        items = response.get("ItemResponse", [])
        total_fetched += len(items)

        for item in items:
            details_items = []
            gtin_lookup = item.get("gtin")
            if gtin_lookup:
                details_response = client.get_item_details(db=db, gtin=gtin_lookup)
                details_items = details_response.get("items", [])

            details = details_items[0] if details_items else {}
            external_id = item.get("wpid")
            sku = item.get("sku")
            brand = details.get("brand")
            title = item.get("productName")
            marketplace_product_type = item.get("productType")
            price_data = item.get("price") or {}
            price = price_data.get("amount")
            currency = price_data.get("currency", "USD")
            gtin = item.get("gtin") or item.get("upc")
            marketplace_item_id = details.get("itemId")
            marketplace_images = [img.get("url") for img in details.get("images", []) if img.get("url")]
            marketplace_customer_rating = details.get("customerRating")
            marketplace_num_reviews = details.get("properties", {}).get("numReviews")
            marketplace_keywords = details.get("properties", {}).get("categories", [])

            listing_status = item.get("lifecycleStatus", "UNKNOWN")

            if not external_id:
                continue

            existing = db.query(MarketplaceListing).filter(
                MarketplaceListing.organization_id == organization_id,
                MarketplaceListing.marketplace == "walmart",
                MarketplaceListing.external_id == external_id,
            ).first()

            if existing:
                existing.marketplace_images = marketplace_images
                existing.marketplace_customer_rating = marketplace_customer_rating
                existing.marketplace_num_reviews = marketplace_num_reviews
                existing.marketplace_keywords = marketplace_keywords
                existing.brand = brand
                existing.marketplace_title = title
                existing.marketplace_sku = sku
                existing.price = Decimal(price) if price else None
                existing.currency = currency
                existing.gtin = gtin
                existing.marketplace_item_id = marketplace_item_id
                existing.listing_status = listing_status
                existing.raw_payload = item
                existing.marketplace_product_type = marketplace_product_type
                existing.updated_at = datetime.now(timezone.utc)
                existing.marketplace_url = generate_walmart_item_url(marketplace_item_id)
                updated_count += 1

            else:
                listing = MarketplaceListing(
                    organization_id=organization_id,
                    marketplace_account_id=marketplace_account.id,
                    marketplace="walmart",
                    external_id=external_id,
                    brand=brand,
                    marketplace_images=marketplace_images,
                    marketplace_customer_rating=marketplace_customer_rating,
                    marketplace_num_reviews=marketplace_num_reviews,
                    marketplace_keywords=marketplace_keywords,
                    marketplace_item_id=marketplace_item_id,
                    marketplace_sku=sku,
                    marketplace_title=title,
                    price=Decimal(price) if price else None,
                    currency=currency,
                    gtin=gtin,
                    listing_status=listing_status,
                    import_status="UNLINKED",
                    raw_payload=item,
                    marketplace_product_type=marketplace_product_type,
                    marketplace_url=generate_walmart_item_url(marketplace_item_id),
                )

                db.add(listing)
                imported_count += 1

        next_cursor = response.get("nextCursor")
        if not next_cursor or not items:
            break

    db.commit()

    return {
        "imported": imported_count,
        "updated": updated_count,
        "skipped": total_fetched - imported_count - updated_count,
        "message": "Import completed",
    }

def get_walmart_inventory(db: Session, marketplace_account, sku):
    client = WalmartClient(marketplace_account)

    response = client.get_inventory(db=db, sku=sku)
    sku = response.get("sku")
    available_quantity = response.get("quantity", {}).get("amount", 0)

    return {"sku": sku, "available_quantity": available_quantity}

