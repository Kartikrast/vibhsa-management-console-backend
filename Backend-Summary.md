
# Vibhsa Management System — Backend Summary

## System Brief

Vibhsa Management System is a **multi-tenant, multi-marketplace management console** built with **FastAPI + SQLAlchemy + PostgreSQL**. It serves as a **single source of truth** for products, inventory, marketplace listings, and orders across connected sales channels (currently Walmart, with an adapter pattern ready for Amazon, Shopify, etc.).

### Core Concepts
- **Multi-tenancy**: Every data row is scoped by `organization_id`. JWT tokens carry `org_id` and every route uses [get_current_context](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/core/dependencies.py:13:0-61:5) to enforce tenant isolation.
- **UUID primary keys**: All models use `UUID(as_uuid=True)` PKs.
- **Marketplace Adapter Pattern**: A generic [MarketplaceOrderAdapter](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/base_adapter.py:4:0-38:11) ABC allows adding new marketplaces without touching core order logic.
- **Periodic Sync + Webhook-ready**: APScheduler runs order imports every N minutes; a webhook endpoint placeholder exists for real-time event ingestion.

### Tech Stack
| Layer | Technology |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (mapped_column) |
| DB | PostgreSQL |
| Migrations | Alembic |
| Auth | JWT (HS256) + Google OAuth |
| Scheduling | APScheduler (BackgroundScheduler) |
| HTTP Client | httpx |
| Validation | Pydantic v2 (pydantic-settings) |
| Package Mgmt | uv + pyproject.toml |


## Folder Structure

```
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
```

---

## Model Structure (Entity-Relationship)

### Auth & Multi-Tenancy
| Model | Table | Key Fields | Relationships |
|---|---|---|---|
| **User** | `users` | `email`, `hashed_password`, `auth_provider`, `provider_user_id`, `is_active`, `is_system_admin` | → OrganizationMembership[] |
| **Organization** | `organizations` | `name`, `slug`, `is_active` | → OrganizationMembership[] |
| **OrganizationMembership** | `organization_memberships` | `user_id` (FK), `organization_id` (FK), `role`, `is_active` | → User, Organization |

### Taxonomy (Master Data)
| Model | Table | Key Fields |
|---|---|---|
| **Category** | `categories` | `name`, `short_code`, `is_active` |
| **SubCategory** | `subcategories` | `name`, `short_code`, `category_id` (FK) |
| **SubSubCategory** | `subsubcategories` | `name`, `short_code`, `subcategory_id` (FK) |
| **ProductType** | `product_types` | `name`, `short_code`, `subsubcategory_id` (FK) |
| **Material** | `materials` | `name`, `short_code` |
| **Color** | `colors` | `name`, `short_code` |
| **Size** | `sizes` | `name`, `short_code` |
| **GoogleTaxonomy** | `google_taxonomy` | `google_id`, `name`, `full_path`, `level` |

### Product (PIM)
| Model | Table | Key Fields | Constraints |
|---|---|---|---|
| **Product** | `products` | `organization_id`, `category_id`, `subcategory_id`, `subsubcategory_id`, `product_type_id`, `material_id`, `product_code`, `product_signature`, `gtin`, `title`, `description`, `bullet_points` (JSONB), `meta_title`, `meta_description`, `seo_keywords` (JSONB), `status` (DRAFT/ACTIVE/PUBLISHED/ARCHIVED) | UQ(org, product_type, product_code), UQ(org, product_signature), UQ(org, gtin) |
| **ProductVariant** | `product_variants` | `product_id` (FK), `organization_id`, `color_id`, `size_id`, `sku`, `barcode`, `weight`, `length`, `width`, `height` | UQ(org, sku), UQ(product, color, size) |
| **ProductTypeCounter** | `product_type_counters` | `organization_id`, `product_type_id`, `current_value` | UQ(org, product_type) |
| **ProductMedia** | `product_media` | `organization_id`, `product_id` (FK nullable), `product_variant_id` (FK nullable), `media_type`, `media_url`, `display_order`, `is_primary` | — |
| **Inventory** | `inventory` | `organization_id`, `product_variant_id`, `location_name`, `quantity_available`, `quantity_reserved` | UQ(org, variant, location) |

### Marketplace
| Model | Table | Key Fields | Constraints |
|---|---|---|---|
| **MarketplaceAccount** | `marketplace_accounts` | `organization_id`, `marketplace` ("walmart"/"amazon"), `seller_id`, `client_id`, `client_secret`, `access_token`, `refresh_token`, `token_expiry`, `is_active` | UQ(org, marketplace) |
| **MarketplaceListing** | `marketplace_listings` | `organization_id`, `marketplace_account_id`, `product_variant_id` (FK nullable), `marketplace`, `external_id`, `marketplace_sku`, `title`, `gtin`, `price`, `currency`, `override_title`, `override_description`, `override_bullet_points`, `import_status` (UNLINKED/LINKED/ARCHIVED), `listing_status`, `sync_status`, `raw_payload` (JSONB) | UQ(org, marketplace, external_id) |

### Orders
| Model | Table | Key Fields | Constraints |
|---|---|---|---|
| **Order** | `orders` | `organization_id`, `marketplace_account_id`, `marketplace`, `external_order_id`, `customer_order_id`, `order_type`, `status` (CREATED/ACKNOWLEDGED/PARTIALLY_SHIPPED/SHIPPED/DELIVERED/CANCELLED), `customer_name/email/phone`, `shipping_address` (JSONB), `shipping_method`, `estimated_ship_date`, `estimated_delivery_date`, `order_date`, `order_total`, `currency`, `raw_payload` (JSONB), `last_synced_at` | UQ(org, marketplace, external_order_id) |
| **OrderLine** | `order_lines` | `order_id` (FK), `organization_id`, `line_number`, `external_sku`, `product_name`, `product_variant_id` (FK nullable), `quantity`, `unit_price`, `shipping_charge`, `tax_amount`, `status` (CREATED/ACKNOWLEDGED/SHIPPED/DELIVERED/CANCELLED/REFUNDED), `cancellation_reason`, `tracking_carrier/number/url`, `ship_date`, `refund_amount`, `raw_line_payload` (JSONB) | UQ(order, line_number) |
| **OrderStatusLog** | `order_status_logs` | `order_id` (FK), `order_line_id` (FK nullable), `previous_status`, `new_status`, `source` (USER/MARKETPLACE_SYNC/SYSTEM/WEBHOOK), `details` (JSONB) | — |

---

## Routes (API Endpoints)

### `/auth` — Authentication
| Method | Path | Description |
|---|---|---|
| POST | `/auth/signup` | Register user + create org + issue JWT |
| POST | `/auth/login` | Email/password login → JWT |
| POST | `/auth/google` | Google OAuth login/signup → JWT |
| GET | `/auth/me` | Current user + org + role |

### `/products` — Product PIM
| Method | Path | Description |
|---|---|---|
| POST | `/products` | Create product (auto-generates SKU, variant, inventory) |
| GET | `/products` | List products (paginated) |
| GET | `/products/{product_id}` | Full product detail (variants, media, listings) |
| PATCH | `/products/{product_id}` | Update PIM fields (title, description, status, GTIN, etc.) |
| POST | `/products/variants/{variant_id}/media` | Upload image/video |
| GET | `/products/variants/{variant_id}/media` | List variant media |
| DELETE | `/products/variants/{variant_id}/media/{media_id}` | Delete media file + DB row |
| POST | `/products/variants/{variant_id}/media/{media_id}/set-primary` | Set primary image |
| POST | `/products/variants/{variant_id}/media/reorder` | Reorder media display_order |

### `/taxonomy` — Master Data
| Method | Path | Description |
|---|---|---|
| GET | `/taxonomy/categories` | All active categories |
| GET | `/taxonomy/subcategories?category_id=` | Subcategories for a category |
| GET | `/taxonomy/subsubcategories?subcategory_id=` | Sub-subcategories |
| GET | `/taxonomy/product-types?subsubcategory_id=` | Product types |
| GET | `/taxonomy/materials` | All materials |
| GET | `/taxonomy/colors` | All colors |
| GET | `/taxonomy/sizes` | All sizes |

### [/marketplaces](cci:9://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces:0:0-0:0) — Marketplace Connections & Listings
| Method | Path | Description |
|---|---|---|
| POST | `/marketplaces/walmart/connect` | Connect Walmart account (validates credentials) |
| GET | `/marketplaces/walmart/items` | Raw Walmart item fetch |
| GET | `/marketplaces/walmart/status` | Connection status check |
| POST | `/marketplaces/walmart/import-listings` | Import Walmart items → MarketplaceListing |
| GET | `/marketplaces/listings` | List imported listings (paginated, filter by status) |
| POST | `/marketplaces/listings/{id}/link-existing` | Link listing to existing product variant |
| POST | `/marketplaces/listings/{id}/generate-internal` | Create new product+variant from listing |

### `/orders` — Order Management
| Method | Path | Description |
|---|---|---|
| POST | `/orders/import` | Trigger order import from all active marketplace accounts |
| GET | `/orders/` | List orders (filter by status, marketplace; paginated) |
| GET | `/orders/{order_id}` | Full order detail with lines |
| POST | `/orders/{order_id}/acknowledge` | Acknowledge → push to marketplace + reserve inventory |
| POST | `/orders/{order_id}/ship` | Ship lines → push tracking + deduct inventory |
| POST | `/orders/{order_id}/cancel` | Cancel lines → push to marketplace + release reservation |
| POST | `/orders/{order_id}/refund` | Refund lines → push to marketplace |
| POST | `/orders/{order_id}/lines/{line_id}/link` | Manually link order line to product variant |
| GET | `/orders/{order_id}/logs` | Audit trail (OrderStatusLog) |

### `/webhooks` — Event Ingestion
| Method | Path | Description |
|---|---|---|
| POST | `/webhooks/walmart/orders` | Placeholder — logs payload, ready for HMAC + dispatch |

---

## Schemas (Pydantic)

| File | Schemas |
|---|---|
| [auth.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/routes/auth.py:0:0-0:0) | [UserCreate](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/auth.py:9:0-11:26), [UserLogin](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/auth.py:13:0-15:17), [Token](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/auth.py:30:0-33:30), [TokenPayload](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/auth.py:36:0-40:12), [GoogleAuthRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/auth.py:25:0-27:26), [UserResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/auth.py:17:0-23:30), [OrganizationInfo](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/auth.py:42:0-48:30), [MeResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/auth.py:51:0-56:13) |
| [product.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/models/product.py:0:0-0:0) | [ProductCreateRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product.py:6:0-15:31), [ProductResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product.py:18:0-24:30), [VariantResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product.py:26:0-34:30), [ProductListResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:128:0-132:14), [ProductListItem](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product.py:48:0-56:30), [PaginatedProductListResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product.py:58:0-62:14) |
| [product_display.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:0:0-0:0) | [SimpleTaxonomyResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:11:0-17:30), [InventoryResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:24:0-30:30), [ProductMediaResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:37:0-45:30), [MarketplaceListingSummaryResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:52:0-60:30), [ProductVariantResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:67:0-79:30), [ProductDetailResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:86:0-110:30), [ProductListItemResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:117:0-125:30), [ProductListResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:128:0-132:14), [ProductStatusEnum](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:135:0-139:25), [UpdateProductRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:142:0-150:52), [ReorderMediaRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:152:0-153:33) |
| [taxonomy.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/routes/taxonomy.py:0:0-0:0) | [SimpleTaxonomyResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/product_display.py:11:0-17:30) |
| [marketplace.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/marketplace.py:0:0-0:0) | [WalmartConnectRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/marketplace.py:4:0-7:22), [WalmartItem](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/marketplace.py:9:0-13:34), [WalmartItemsResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/marketplace.py:16:0-17:28) |
| [marketplace_listing.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/models/marketplace_listing.py:0:0-0:0) | [MarketplaceListingResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/marketplace_listing.py:7:0-21:30), [ImportResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/marketplace_listing.py:23:0-27:33), [LinkListingRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/marketplace_listing.py:29:0-30:28) |
| [listing_link.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/listing_link.py:0:0-0:0) | [LinkExistingListingRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/listing_link.py:4:0-5:28), [GenerateFromListingRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/listing_link.py:7:0-14:17), [ListingLinkResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/listing_link.py:16:0-19:21) |
| [order.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/models/order.py:0:0-0:0) | [OrderLineResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:9:0-30:44), [OrderListResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:37:0-51:44), [OrderDetailResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:54:0-78:44), [ShipLineRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:85:0-89:35), [ShipOrderRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:92:0-93:32), [CancelLineRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:96:0-98:46), [CancelOrderRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:101:0-102:34), [RefundLineRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:105:0-107:17), [RefundOrderRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:110:0-111:34), [LinkOrderLineRequest](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:114:0-115:28), [OrderStatusLogResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:122:0-132:44), [OrderImportResponse](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/schemas/order.py:139:0-143:16) |

---

## Key Architectural Patterns

### 1. Multi-Tenancy Enforcement
Every protected route calls [get_current_context](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/core/dependencies.py:13:0-61:5) which decodes the JWT, loads User + Organization + Membership, and returns a dict:
```python
{"user": User, "organization": Organization, "role": str}
```
All queries then filter by `organization.id`.

### 2. Marketplace Adapter Pattern
```
MarketplaceOrderAdapter (ABC)           ← base_adapter.py
    ├── fetch_new_orders()
    ├── fetch_order()
    ├── acknowledge_order()
    ├── ship_order()
    ├── cancel_order()
    └── refund_order()

WalmartOrderAdapter                     ← walmart/order_adapter.py
    └── implements all 6 methods + _normalize_order()

adapter_registry.py
    └── get_order_adapter("walmart", account) → WalmartOrderAdapter
```
The [order_service.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/services/order_service.py:0:0-0:0) and `order_import_service.py` **never import marketplace-specific code**. They resolve the adapter via the registry.

### 3. Inventory Hooks (Order Lifecycle)
| Action | Inventory Effect |
|---|---|
| Acknowledge | `reserve_inventory` (+qty_reserved) |
| Ship | `deduct_inventory` (−qty_available, −qty_reserved) |
| Cancel | `release_reservation` (−qty_reserved) |

All use `SELECT ... FOR UPDATE` for concurrency safety.

### 4. Order Status Derivation
Header-level `Order.status` is **derived** from all `OrderLine.status` values after each action (e.g., if all lines are SHIPPED → Order is SHIPPED; if mixed → PARTIALLY_SHIPPED).

---

## Next Steps: Amazon Marketplace Integration

### What's Needed

#### 1. Amazon API Client — `app/marketplaces/amazon/client.py`
Create an `AmazonClient` class similar to `WalmartClient`:
- **Auth**: Amazon SP-API uses **LWA (Login with Amazon)** OAuth 2.0 with `refresh_token` grant type. You'll need:
  - `LWA_CLIENT_ID`, `LWA_CLIENT_SECRET`, `LWA_REFRESH_TOKEN` per account
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ROLE_ARN` for STS signing
  - SP-API endpoints are signed with **AWS Signature V4** (use `requests-aws4auth` or `boto3`)
- **Config additions** to [app/core/config.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/core/config.py:0:0-0:0):
  ```python
  AMAZON_SP_API_ENDPOINT: str = "https://sellingpartnerapi-na.amazon.com"
  AMAZON_LWA_ENDPOINT: str = "https://api.amazon.com/auth/o2/token"
  ```
- **Key order methods** to implement (matching Walmart's pattern):
  - `get_orders(created_after, order_statuses, ...)` → SP-API `GET /orders/v0/orders`
  - `get_order(order_id)` → `GET /orders/v0/orders/{orderId}`
  - `get_order_items(order_id)` → `GET /orders/v0/orders/{orderId}/orderItems`
  - Amazon does **not** have an explicit "acknowledge" call — orders move to `Unshipped` automatically
  - `create_feed(feed_type, content)` → `POST /feeds/2021-06-30/feeds` (used for ship confirm & cancellation)
  - Ship confirmation and cancellation use **Feed API** with XML payloads (`POST_ORDER_FULFILLMENT_DATA`, `POST_ORDER_ACKNOWLEDGEMENT_DATA`)

#### 2. Amazon Order Adapter — `app/marketplaces/amazon/order_adapter.py`
Implement [MarketplaceOrderAdapter](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/base_adapter.py:4:0-38:11):

| Method | Amazon Implementation |
|---|---|
| [fetch_new_orders()](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/walmart/order_adapter.py:17:4-31:65) | Call `get_orders(order_statuses=["Unshipped"])` + `get_order_items()` per order; normalize into the same dict format as Walmart |
| [fetch_order()](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/walmart/order_adapter.py:33:4-37:47) | `get_order()` + `get_order_items()` |
| [acknowledge_order()](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/walmart/order_adapter.py:39:4-41:88) | No-op or submit `POST_ORDER_ACKNOWLEDGEMENT_DATA` feed |
| [ship_order()](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/walmart/order_adapter.py:43:4-75:9) | Submit `POST_ORDER_FULFILLMENT_DATA` feed with tracking info |
| [cancel_order()](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/walmart/order_adapter.py:77:4-114:9) | Submit order cancellation feed |
| [refund_order()](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/walmart/order_adapter.py:116:4-159:9) | Not feed-based — Amazon manages refunds through Seller Central or the Refunds API |

**Normalization** ([_normalize_order](cci:1://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/walmart/order_adapter.py:165:4-255:9)): Map Amazon's response fields to the same dict shape:
```python
{
    "external_order_id": AmazonOrderId,
    "customer_order_id": AmazonOrderId,
    "order_date_ms": PurchaseDate (ISO → ms),
    "customer_name": ShippingAddress.Name,
    "shipping_address": { ... },
    "lines": [
        {
            "line_number": OrderItemId,
            "external_sku": SellerSKU,
            "product_name": Title,
            "quantity": QuantityOrdered,
            "unit_price": ItemPrice.Amount,
            ...
        }
    ],
    "raw": <original response>,
}
```

#### 3. Register in Adapter Registry — [app/marketplaces/adapter_registry.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/adapter_registry.py:0:0-0:0)
Add one `elif` block:
```python
elif marketplace == "amazon":
    from app.marketplaces.amazon.order_adapter import AmazonOrderAdapter
    return AmazonOrderAdapter(account)
```

#### 4. MarketplaceAccount Row
When connecting Amazon, create a [MarketplaceAccount](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/models/marketplace_account.py:18:0-95:5) row with `marketplace="amazon"` and store:
- `seller_id` → Amazon Seller/Merchant ID
- `client_id` → LWA Client ID
- `client_secret` → LWA Client Secret
- `refresh_token` → LWA Refresh Token
- Add a new JSONB column or use existing fields for AWS credentials (`aws_access_key_id`, `aws_secret_access_key`, `role_arn`)

#### 5. Connect Route — [app/routes/marketplaces.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/routes/marketplaces.py:0:0-0:0)
Add `POST /marketplaces/amazon/connect` endpoint (similar to Walmart connect):
- Accept Amazon credentials
- Validate by calling the LWA token endpoint
- Store tokens in [MarketplaceAccount](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/models/marketplace_account.py:18:0-95:5)

#### 6. Listing Import (Optional) — `app/services/marketplace_import/amazon_import.py`
Similar to `walmart_import.py` — call SP-API Catalog Items or Listings API to import Amazon listings into [MarketplaceListing](cci:2://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/models/marketplace_listing.py:29:0-200:5).

#### 7. Webhook Endpoint — [app/routes/webhooks.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/routes/webhooks.py:0:0-0:0)
Add `POST /webhooks/amazon/orders` — Amazon uses **SQS/EventBridge notifications** rather than direct HTTP webhooks. You may need an SQS poller or EventBridge subscription instead.

#### 8. Dependencies to Add
```
python-amazon-sp-api   # or build raw client with requests + aws4auth
boto3                  # for STS AssumeRole + SigV4 signing
```

#### 9. Files to Create/Modify Summary
| Action | File |
|---|---|
| **Create** | `app/marketplaces/amazon/__init__.py` |
| **Create** | `app/marketplaces/amazon/client.py` |
| **Create** | `app/marketplaces/amazon/order_adapter.py` |
| **Create** | `app/services/marketplace_import/amazon_import.py` |
| **Modify** | [app/marketplaces/adapter_registry.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/marketplaces/adapter_registry.py:0:0-0:0) (add `"amazon"` case) |
| **Modify** | [app/core/config.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/core/config.py:0:0-0:0) (add Amazon env vars) |
| **Modify** | [app/routes/marketplaces.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/routes/marketplaces.py:0:0-0:0) (add Amazon connect/import routes) |
| **Modify** | [app/routes/webhooks.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/routes/webhooks.py:0:0-0:0) (add Amazon webhook/SQS placeholder) |
| **Possibly modify** | [app/models/marketplace_account.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/models/marketplace_account.py:0:0-0:0) (add JSONB for AWS creds if needed) |

**No changes needed** to: [order.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/models/order.py:0:0-0:0) (models), [order_service.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/services/order_service.py:0:0-0:0), `order_import_service.py`, [inventory_service.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/services/inventory_service.py:0:0-0:0), [order_sync.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/tasks/order_sync.py:0:0-0:0), or [orders.py](cci:7://file:///c:/Users/karti/Documents/work_projects/vibhsa_management_system/backend/app/routes/orders.py:0:0-0:0) (routes). The adapter pattern handles everything.