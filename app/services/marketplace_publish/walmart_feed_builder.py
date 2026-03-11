from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.marketplace_listing import MarketplaceListing


def build_walmart_item_feed(
    product: Product,
    variant: ProductVariant,
    listing: MarketplaceListing,
):

    title = listing.override_title or product.title
    description = listing.override_description or product.description
    bullet_points = (
        listing.override_bullet_points
        if listing.override_bullet_points
        else product.bullet_points
    )

    item = {
        "Orderable": {
            "sku": variant.sku,
            "productIdentifiers": {
                "productIdType": "GTIN",
                "productId": product.gtin,
            },
        },
        "Visible": {
            "productName": title,
            "shortDescription": description,
            "keyFeatures": bullet_points or [],
        },
    }

    payload = {
        "MPItemFeedHeader": {
            "version": "5.0.20250121-19_24_23-api",
            "locale": "en",
            "businessUnit": "WALMART_US",
        },
        "MPItem": [item],
    }

    return payload