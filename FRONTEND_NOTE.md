# Frontend Implementation Note — Walmart Reports & Listing Quality

## 1. Report Generation

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/marketplaces/walmart/report-types` | Get available report types and their versions |
| `POST` | `/marketplaces/walmart/reports` | Create a new report request |
| `GET` | `/marketplaces/walmart/reports` | List all report requests (supports `status_filter`, `limit`, `offset`) |
| `GET` | `/marketplaces/walmart/reports/{report_id}` | Get a single report request by ID |
| `POST` | `/marketplaces/walmart/reports/{report_id}/refresh` | Refresh/poll the status of a report |

### Create Report — Request Body

```json
{
  "report_type": "ITEM",
  "report_version": "v1",
  "data_start_time": "2026-04-01T00:00:00Z",
  "data_end_time": "2026-04-10T00:00:00Z",
  "row_filters": null,
  "exclude_columns": null
}
```

### Report Response Shape

```json
{
  "id": "uuid",
  "external_request_id": "walmart-id",
  "report_type": "ITEM",
  "report_version": "v1",
  "data_start_time": "2026-04-01T00:00:00+00:00",
  "data_end_time": "2026-04-10T00:00:00+00:00",
  "status": "PENDING | IN_PROGRESS | COMPLETED | FAILED",
  "download_url": "https://...",
  "expires_at": "2026-04-17T...",
  "completed_at": "2026-04-10T...",
  "failed_at": null,
  "error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

### Suggested UI Flow

1. **Report Types dropdown** — Call `GET /walmart/report-types` on page load to populate a selector. Each type has a `name`, `type`, and a list of `versions`.
2. **Create Report form** — User picks report type, version, date range → `POST /walmart/reports`.
3. **Reports list table** — Call `GET /walmart/reports` to display all past and in-progress reports with columns: Type, Status, Created, Download link.
4. **Polling / Refresh** — While status is `PENDING` or `IN_PROGRESS`, either auto-poll or show a "Refresh" button that calls `POST /walmart/reports/{id}/refresh`.
5. **Download** — When status is `COMPLETED`, the `download_url` field contains a direct download link. Show it as a clickable button/link.

---

## 2. Listing Quality (Per-Listing)

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/marketplaces/listings/{listing_id}/quality` | **Read stored quality from DB** (fast, no Walmart API call) |
| `POST` | `/marketplaces/listings/{listing_id}/sync-quality` | **Sync quality from Walmart API** for a single listing and store in DB |
| `GET` | `/marketplaces/walmart/listing-quality` | Seller-level overall quality score |
| `POST` | `/marketplaces/walmart/listing-quality/items` | Raw item-level quality details from Walmart (pass-through, not stored) |
| `POST` | `/marketplaces/walmart/sync-listing-content` | Bulk sync all items (use sparingly) |

### Recommended Flow (when user selects a listing)

1. **First, read from DB** — call `GET /marketplaces/listings/{listing_id}/quality`
2. **If `has_quality_data` is `false`**, or the user clicks a "Refresh" button → call `POST /marketplaces/listings/{listing_id}/sync-quality`
3. **Then re-fetch** from DB with the GET endpoint to display updated data

This avoids hitting the Walmart API on every listing click (rate-limit friendly).

### GET /listings/{listing_id}/quality — Response

Returns stored data from DB (no API call):

```json
{
  "listing_id": "uuid",
  "marketplace_sku": "elephantwhite",
  "quality_score": 72.0,
  "quality_data": {
    "sku": "elephantwhite",
    "productName": "Vibhsa Handmade Ring Holder...",
    "score": {
      "overallScore": 72,
      "details": {
        "contentQuality": {
          "score": 80,
          "attributes": [
            { "name": "product_short_description", "value": "The product description..." },
            { "name": "product_long_description", "value": "<ul><li>Bullet 1</li><li>Bullet 2</li></ul>" },
            { "name": "images", "value": "4" }
          ]
        },
        "offerQuality": { "score": 65, "attributes": [...] }
      }
    }
  },
  "marketplace_description": "The product description...",
  "marketplace_bullet_points": ["Bullet 1", "Bullet 2"],
  "has_quality_data": true
}
```

**If quality has never been synced**, `quality_data` and `quality_score` will be `null` and `has_quality_data` will be `false`.

### POST /listings/{listing_id}/sync-quality — Response

Fetches fresh data from Walmart API, stores it in DB, and returns:

```json
{
  "updated": true,
  "listing_id": "uuid",
  "quality_score": 72.0,
  "message": "Listing quality synced"
}
```

If Walmart has no data for the SKU:

```json
{
  "updated": false,
  "message": "No quality data returned for this SKU"
}
```

### What to Display

| Data Point | Source in GET response | Display |
|------------|----------------------|---------|
| Overall quality score | `quality_score` | Score badge/progress bar (e.g. 72/100) |
| Content quality score | `quality_data.score.details.contentQuality.score` | Sub-score |
| Offer quality score | `quality_data.score.details.offerQuality.score` | Sub-score |
| Description | `marketplace_description` | Text block (already extracted by backend) |
| Bullet points | `marketplace_bullet_points` | Render as list (already extracted by backend) |
| Image count | `quality_data.score.details.contentQuality.attributes` → `images` | e.g. "4 images" (actual URLs come from listing's `marketplace_images`) |
| Content issues | Attributes in `contentQuality.attributes` with low scores | Highlight missing/poor attributes |
| Offer issues | Attributes in `offerQuality.attributes` | Highlight pricing/shipping issues |

### Listings Table

The `listing_quality_score` field is now included in the listings list response (`GET /marketplaces/listings`). You can show a quality score column in the listings table without any additional API call.

### DB Fields Stored Per Listing

| Field | Type | Description |
|-------|------|-------------|
| `listing_quality_data` | JSONB | Full raw Walmart quality API response for this item |
| `listing_quality_score` | Numeric | The `overallScore` value (e.g. 72.00) |
| `marketplace_description` | Text | Extracted from `product_short_description` |
| `marketplace_bullet_points` | JSONB | Extracted from `product_long_description` HTML (array of strings) |

---

## 3. Rate Limiting (429 Handling)

All Walmart endpoints may return `429 Too Many Requests` when the API rate limit is exhausted.

**Error response:**

```json
{
  "detail": {
    "error": "rate_limit_exceeded",
    "remaining_tokens": 0,
    "max_tokens": 10,
    "next_replenishment_time": "2026-04-10T14:30:00+00:00",
    "retry_after_seconds": 45
  }
}
```

**Frontend handling:**
- Check for HTTP 429 status on all `/walmart/*` calls.
- Display a user-friendly message: _"Walmart API rate limit reached. Please try again in {retry_after_seconds} seconds."_
- Optionally show a countdown timer using `retry_after_seconds`.
- Disable the action button until the timer expires.
