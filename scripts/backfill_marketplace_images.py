"""
One-time backfill: import marketplace_images into product_media
for all LINKED listings whose variants have no media yet.

Usage:
    python -m scripts.backfill_marketplace_images
"""

from app.core.database import SessionLocal
from app.models.marketplace_listing import MarketplaceListing
from app.models.product_media import ProductMedia


def backfill():
    db = SessionLocal()

    try:
        listings = (
            db.query(MarketplaceListing)
            .filter(
                MarketplaceListing.import_status == "LINKED",
                MarketplaceListing.product_variant_id.isnot(None),
                MarketplaceListing.marketplace_images.isnot(None),
            )
            .all()
        )

        created = 0
        skipped = 0

        for listing in listings:
            images = listing.marketplace_images
            if not images:
                skipped += 1
                continue

            # Skip if variant already has media
            existing_count = (
                db.query(ProductMedia)
                .filter(
                    ProductMedia.product_variant_id == listing.product_variant_id,
                    ProductMedia.organization_id == listing.organization_id,
                )
                .count()
            )

            if existing_count > 0:
                skipped += 1
                continue

            for i, url in enumerate(images):
                order = i + 1
                media = ProductMedia(
                    organization_id=listing.organization_id,
                    product_variant_id=listing.product_variant_id,
                    media_type="image",
                    media_url=url,
                    display_order=order,
                    is_primary=(order == 1),
                )
                db.add(media)
                created += 1

        db.commit()
        print(f"Backfill complete: {created} media rows created, {skipped} listings skipped")

    finally:
        db.close()


if __name__ == "__main__":
    backfill()
