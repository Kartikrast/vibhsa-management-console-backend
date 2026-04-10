import re
from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from app.models.marketplace_listing import MarketplaceListing
from app.marketplaces.walmart.client import WalmartClient, WalmartRateLimitError
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


def _parse_html_bullets(html: str) -> list[str]:
    """Extract bullet point texts from HTML <li> tags."""
    items = re.findall(r"<li[^>]*>(.*?)</li>", html, re.DOTALL | re.IGNORECASE)
    # Strip any remaining HTML tags and whitespace from each item
    clean = []
    for item in items:
        text = re.sub(r"<[^>]+>", "", item).strip()
        if text:
            clean.append(text)
    return clean


def _extract_content_attributes(item_data: dict) -> dict:
    """Extract description and bullet points from Walmart listing quality item data.

    - product_short_description → marketplace_description
    - product_long_description (HTML with <li> tags) → marketplace_bullet_points
    """
    result = {"description": None, "bullet_points": None}

    score_details = item_data.get("score", {}).get("details", {})
    content_quality = score_details.get("contentQuality", {})
    attributes = content_quality.get("attributes", [])

    for attr in attributes:
        name = attr.get("name", "")
        value = attr.get("value")
        if not value:
            continue

        if name == "product_short_description":
            result["description"] = value
        elif name == "product_long_description":
            bullets = _parse_html_bullets(value)
            if bullets:
                result["bullet_points"] = bullets

    return result


def sync_listing_content_from_quality(
    db: Session,
    organization_id: UUID,
    marketplace_account,
) -> dict:
    """Fetch listing quality data from Walmart and sync content into listings.

    Stores raw quality JSON, quality score, description, and bullet points.
    """
    client = WalmartClient(marketplace_account)

    updated_count = 0
    total_processed = 0
    next_cursor = None

    while True:
        response = client.get_item_listing_quality_details(
            db=db,
            limit=200,
            next_cursor=next_cursor,
        )

        items = response.get("payload", [])
        total_processed += len(items)

        for item_data in items:
            sku = item_data.get("sku")
            if not sku:
                continue

            listing = db.query(MarketplaceListing).filter(
                MarketplaceListing.organization_id == organization_id,
                MarketplaceListing.marketplace == "walmart",
                MarketplaceListing.marketplace_sku == sku,
            ).first()

            if not listing:
                continue

            # Store raw quality data
            listing.listing_quality_data = item_data

            # Store quality score
            quality_score = item_data.get("score", {}).get("overallScore")
            if quality_score is not None:
                try:
                    listing.listing_quality_score = Decimal(str(quality_score))
                except (ValueError, TypeError):
                    pass

            # Extract and store content attributes
            content = _extract_content_attributes(item_data)

            if content["description"] and not listing.marketplace_description:
                listing.marketplace_description = content["description"]

            if content["bullet_points"] and not listing.marketplace_bullet_points:
                listing.marketplace_bullet_points = content["bullet_points"]

            updated_count += 1

        next_cursor = response.get("meta", {}).get("nextCursor")
        if not next_cursor or not items:
            break

    db.commit()

    return {
        "total_processed": total_processed,
        "updated": updated_count,
        "message": "Listing quality content sync completed",
    }


def sync_single_listing_quality(
    db: Session,
    listing: MarketplaceListing,
    marketplace_account,
) -> dict:
    """Fetch and store listing quality data for a single listing."""
    client = WalmartClient(marketplace_account)

    response = client.get_item_listing_quality_details(
        db=db,
        limit=1,
        payload={"query": {"field": "sku", "value": listing.marketplace_sku}},
    )

    items = response.get("payload", [])
    if not items:
        return {"updated": False, "message": "No quality data returned for this SKU"}

    item_data = items[0]

    # Store raw quality data
    listing.listing_quality_data = item_data

    # Store quality score
    quality_score = item_data.get("score", {}).get("overallScore")
    if quality_score is not None:
        try:
            listing.listing_quality_score = Decimal(str(quality_score))
        except (ValueError, TypeError):
            pass

    # Extract and store content attributes
    content = _extract_content_attributes(item_data)

    if content["description"]:
        listing.marketplace_description = content["description"]

    if content["bullet_points"]:
        listing.marketplace_bullet_points = content["bullet_points"]

    db.commit()
    db.refresh(listing)

    return {
        "updated": True,
        "listing_id": str(listing.id),
        "quality_score": float(listing.listing_quality_score) if listing.listing_quality_score else None,
        "message": "Listing quality synced",
    }

