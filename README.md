backend/
├── alembic/                        # Alembic migration config + versions
│   ├── versions/                   # Migration scripts
│   └── env.py
├── app/
│   ├── core/
│   │   ├── config.py               # Settings (env-based): DB, JWT, Walmart, sync interval
│   │   ├── database.py             # SQLAlchemy engine + SessionLocal + get_db dependency
│   │   ├── dependencies.py         # get_current_context (JWT → user + org + role)
│   │   └── security.py             # create_access_token, decode_token, hash/verify password
│   ├── marketplaces/
│   │   ├── base_adapter.py         # MarketplaceOrderAdapter ABC (6 abstract methods)
│   │   ├── adapter_registry.py     # get_order_adapter(marketplace, account) → adapter
│   │   └── walmart/
│   │       ├── client.py           # WalmartClient: auth, items, orders (7 order methods)
│   │       └── order_adapter.py    # WalmartOrderAdapter: implements ABC + normalizes responses
│   ├── models/
│   │   ├── __init__.py             # Registers all models for Alembic discovery
│   │   ├── base.py                 # declarative Base
│   │   ├── user.py                 # User
│   │   ├── organization.py         # Organization
│   │   ├── organization_membership.py  # OrganizationMembership (user ↔ org, role)
│   │   ├── taxonomy.py             # Category, SubCategory, SubSubCategory, ProductType, Material, Color, Size
│   │   ├── google_taxonomy.py      # GoogleTaxonomy (imported from Google's product taxonomy)
│   │   ├── product.py              # Product (PIM: title, description, bullets, SEO, status)
│   │   ├── product_variant.py      # ProductVariant (SKU, color, size, dimensions)
│   │   ├── product_counter.py      # ProductTypeCounter (auto-incrementing product codes)
│   │   ├── product_media.py        # ProductMedia (images/videos per product or variant)
│   │   ├── inventory.py            # Inventory (qty_available, qty_reserved per variant+location)
│   │   ├── marketplace_account.py  # MarketplaceAccount (credentials, tokens per org)
│   │   ├── marketplace_listing.py  # MarketplaceListing (external listings linked to variants)
│   │   └── order.py                # Order, OrderLine, OrderStatusLog + enums
│   ├── routes/
│   │   ├── auth.py                 # /auth — signup, login, google, me
│   │   ├── products.py             # /products — CRUD, media upload/delete/reorder
│   │   ├── taxonomy.py             # /taxonomy — categories, subcategories, product-types, etc.
│   │   ├── marketplaces.py         # /marketplaces — connect, import listings, link
│   │   ├── orders.py               # /orders — import, list, detail, acknowledge, ship, cancel, refund, link, logs
│   │   └── webhooks.py             # /webhooks — Walmart order event placeholder
│   ├── schemas/
│   │   ├── auth.py                 # UserCreate, UserLogin, Token, MeResponse, etc.
│   │   ├── product.py              # ProductCreateRequest, ProductResponse, PaginatedProductListResponse
│   │   ├── product_display.py      # ProductDetailResponse, UpdateProductRequest, MediaResponse, etc.
│   │   ├── product_bulk.py         # Bulk operation schemas
│   │   ├── taxonomy.py             # SimpleTaxonomyResponse
│   │   ├── marketplace.py          # WalmartConnectRequest, WalmartItemsResponse
│   │   ├── marketplace_listing.py  # MarketplaceListingResponse, ImportResponse
│   │   ├── listing_link.py         # LinkExistingListingRequest, GenerateFromListingRequest
│   │   └── order.py                # OrderListResponse, OrderDetailResponse, Ship/Cancel/Refund schemas
│   ├── services/
│   │   ├── auth_service.py         # authenticate_user, issue_tokens
│   │   ├── google_oauth.py         # verify_google_token
│   │   ├── product_service.py      # create_product (auto-generates SKU, variant, inventory)
│   │   ├── marketplace_linking_service.py  # link_existing_listing, generate_internal_from_listing
│   │   ├── inventory_service.py    # reserve_inventory, deduct_inventory, release_reservation (SELECT FOR UPDATE)
│   │   ├── order_service.py        # acknowledge, ship, cancel, refund, link_order_line_to_variant
│   │   ├── marketplace_import/
│   │   │   └── walmart_import.py   # import_walmart_listings (items → MarketplaceListing)
│   │   └── order_import/
│   │       └── order_import_service.py  # import_orders (adapter-agnostic upsert + SKU auto-linking)
│   ├── tasks/
│   │   └── order_sync.py           # sync_all_orders (background job for all active accounts)
│   └── utils/
│       ├── gtin.py                 # GTIN validation helper
│       └── slug.py                 # generate_slug
├── scripts/
│   ├── import_google_taxonomy.py   # Imports Google's product taxonomy into GoogleTaxonomy table
│   ├── flatten_google_taxonomy.py  # Flattens Google taxonomy → Category/Sub/SubSub/ProductType
│   └── seed_master_data.py         # Seeds Materials, Colors, Sizes
├── data/
│   └── google_taxonomy.txt         # Raw Google taxonomy file
├── media/                          # Uploaded product media files
├── .env                            # Environment variables
├── alembic.ini
└── pyproject.toml                  # Dependencies (uv)