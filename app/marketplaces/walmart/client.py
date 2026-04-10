import httpx
import uuid
import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from typing import Optional

from app.core.config import get_settings

settings = get_settings()

DEFAULT_BOX = {
    "boxWeightUnit": "OZ", "boxLength": 6, "boxWidth": 6,
    "boxHeight": 4, "boxWeight": 16, "boxDimensionUnit": "IN"
}


class WalmartRateLimitError(Exception):
    """Raised when Walmart API returns a 429 rate limit response."""

    def __init__(self, remaining_tokens: int, max_tokens: int, next_replenishment_time: Optional[datetime]):
        self.remaining_tokens = remaining_tokens
        self.max_tokens = max_tokens
        self.next_replenishment_time = next_replenishment_time
        super().__init__(f"Walmart API rate limit exceeded. Remaining tokens: {remaining_tokens}/{max_tokens}. Replenishes at: {next_replenishment_time}")


class WalmartClient:
    def __init__(self, account=None, client_id=None, client_secret=None):
        """
        account → MarketplaceAccount (normal usage)
        OR
        client_id + client_secret → bootstrap mode (connect flow)
        """
        self.account = account

        if account:
            self.client_id = account.client_id
            self.client_secret = account.client_secret
        else:
            self.client_id = client_id
            self.client_secret = client_secret

        if settings.WALMART_ENV == "production":
            self.base_url = settings.WALMART_PRODUCTION_URL
        else:
            self.base_url = settings.WALMART_SANDBOX_URL

    def _get_headers(self, include_basic_auth: bool = False):
        headers = {
            "WM_SEC.ACCESS_TOKEN": self.account.access_token,
            "WM_SVC.NAME": "Vibhsa",
            "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
            "WM_CONSUMER.CHANNEL.TYPE": self.account.seller_id,  # from Walmart portal
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if include_basic_auth:
            encoded_credentials = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {encoded_credentials}"
        return headers

    def _refresh_token_if_needed(self, db):
        if not self.account.token_expiry:
            return

        if datetime.now(timezone.utc) < self.account.token_expiry:
            return  # still valid

        # refresh token
        response = httpx.post(
            f"{self.base_url}/v3/token",
            data={"grant_type": "client_credentials"},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "WM_SVC.NAME": "Vibhsa",
                "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
            },
            auth=(self.client_id, self.client_secret),
        )

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        token_data = response.json()

        self.account.access_token = token_data["access_token"]
        self.account.token_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=token_data["expires_in"]
        )

        db.commit()
    
    def get_access_token(self):
        response = httpx.post(
            f"{self.base_url}/v3/token",
            data={"grant_type": "client_credentials"},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "WM_SVC.NAME": "Vibhsa",
                "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
            },
            auth=(self.client_id, self.client_secret),
        )

        if response.status_code != 200:
            raise Exception(f"Token generation failed: {response.text}")

        return response.json()

    def _parse_rate_limit_headers(self, response: httpx.Response) -> Optional[dict]:
        """Parse Walmart rate limit headers from response."""
        headers = response.headers
        current_tokens = headers.get("x-current-token-count")
        max_tokens = headers.get("x-max-token-count")
        next_replenishment = headers.get("x-next-replenishment-time")

        if not current_tokens or not max_tokens:
            return None

        try:
            current = int(current_tokens)
            max_t = int(max_tokens)
            replenish_time = None
            if next_replenishment:
                # Assuming ISO format, adjust if needed
                replenish_time = datetime.fromisoformat(next_replenishment.replace('Z', '+00:00'))
            return {
                "remaining_tokens": current,
                "max_tokens": max_t,
                "next_replenishment_time": replenish_time
            }
        except (ValueError, TypeError):
            return None

    def request(self, method, endpoint, db, include_basic_auth: bool = False, **kwargs):
        """
        Centralized request method
        """
        self._refresh_token_if_needed(db)

        url = f"{self.base_url}{endpoint}"

        response = httpx.request(
            method,
            url,
            headers=self._get_headers(include_basic_auth=include_basic_auth),
            timeout=30.0,
            **kwargs,
        )

        if response.status_code == 429:
            # Parse rate limit info and raise specific exception
            rate_limit_info = self._parse_rate_limit_headers(response)
            if rate_limit_info:
                raise WalmartRateLimitError(
                    remaining_tokens=rate_limit_info["remaining_tokens"],
                    max_tokens=rate_limit_info["max_tokens"],
                    next_replenishment_time=rate_limit_info["next_replenishment_time"]
                )
            else:
                raise Exception(f"Walmart API rate limit exceeded: {response.text}")

        if response.status_code >= 400:
            raise Exception(f"Walmart API error: {response.text}")

        return response.json()
    
    # ========================
    # LISTINGS MANAGEMENT
    # ========================

    def get_seller_listing_quality(self, db):
        """
        Get seller listing quality
        GET /v3/insights/items/listingQuality/score
        """
        endpoint = "/v3/insights/items/listingQuality/score"
        return self.request(method="GET", endpoint=endpoint, db=db, include_basic_auth=True)

    def get_item_listing_quality_details(self, db, limit: int = 200, next_cursor: str = None, payload: dict = None):
        """
        Get item-level listing quality details.
        POST /v3/insights/items/listingQuality/items

        Returns item quality score, offer score, content score and issues,
        and item performance for each item.

        Query params:
            limit: number of items to return (default 200)
            nextCursor: pagination cursor from previous response

        Request body (optional):
            payload with filters, e.g.:
            {
                "query": {
                    "filters": [...]
                }
            }
        """
        endpoint = f"/v3/insights/items/listingQuality/items?limit={limit}"
        if next_cursor:
            endpoint += f"&nextCursor={quote(next_cursor, safe='')}"

        kwargs = {}
        if payload:
            kwargs["json"] = payload

        return self.request(
            method="POST",
            endpoint=endpoint,
            db=db,
            include_basic_auth=True,
            **kwargs,
        )
        
    def get_items(self, db, limit: int = 50, next_cursor: str = None):
        """
        Fetch product listings from Walmart.
        """
        endpoint = f"/v3/items?limit={limit}"
        if next_cursor:
            endpoint += f"&nextCursor={quote(next_cursor, safe='')}"

        return self.request(
            method="GET",
            endpoint=endpoint,
            db=db,
        )
    
    def get_item(self, db, sku: str):
        """
        Fetch item details by SKU
        GET /v3/items/{sku}
        """
        endpoint = f"/v3/items/{sku}"
        return self.request(method="GET", endpoint=endpoint, db=db)
    
    def get_item_details(self, db, gtin: str):
        """
        Fetch item details by GTIN
        GET /v3/items/walmart/search?gtin={gtin}
        """
        endpoint = f"/v3/items/walmart/search?gtin={gtin}"
        return self.request(method="GET", endpoint=endpoint, db=db)

    # ========================
    # INVENTORY MANAGEMENT
    # ========================
    def get_inventory(self, db, sku: str):
        """
        Fetch inventory details for a SKU.
        GET /v3/inventory?sku={sku}
        """
        endpoint = f"/v3/inventory?sku={sku}"
        return self.request(method="GET", endpoint=endpoint, db=db)
    
    def update_inventory(self, db, sku: str, quantity: int):
        """
        Update inventory quantity for a SKU.
        PUT /v3/inventory

        Payload:
        {
            "sku": "SKU123",
            "quantity": 10,
        }
        """
        endpoint = "/v3/inventory"
        payload = {
        "sku": sku,
        "quantity": {
            "unit": "EACH",
            "amount": quantity
            }
        }
        return self.request(method="PUT", endpoint=endpoint, db=db, json=payload)
    
    # ========================
    # FEED MANAGEMENT
    # ========================

    def submit_feed(self, db, feed_type: str, payload: dict):
        """
        Submit a Walmart feed.

        POST /v3/feeds

        feed_type examples:
        MP_ITEM
        MP_INVENTORY
        MP_PRICE
        """

        endpoint = "/v3/feeds"

        params = {
            "feedType": feed_type
        }

        return self.request(
            method="POST",
            endpoint=endpoint,
            db=db,
            params=params,
            json=payload,
        )
    
    def get_feed_status(self, db, feed_id: str):
        """
        Check Walmart feed processing status.

        GET /v3/feeds/{feedId}
        """

        endpoint = f"/v3/feeds/{feed_id}"

        return self.request(
            method="GET",
            endpoint=endpoint,
            db=db,
        )
    
    def get_feed_item_status(self, db, feed_id: str, offset: int = 0, limit: int = 50):
        """
        Fetch item level status for a feed.

        GET /v3/feeds/{feedId}/items
        """

        endpoint = f"/v3/feeds/{feed_id}/items?offset={offset}&limit={limit}"

        return self.request(
            method="GET",
            endpoint=endpoint,
            db=db,
        )

    # ========================
    # ORDER MANAGEMENT
    # ========================

    def get_released_orders(self, db, limit: int = 100):
        """
        Fetch orders with line items in Created status that are released for processing.
        GET /v3/orders/released
        """
        endpoint = f"/v3/orders/released?limit={limit}"
        return self.request(method="GET", endpoint=endpoint, db=db)

    def get_all_orders(
        self,
        db,
        status: str | None = None,
        created_start_date: str | None = None,
        created_end_date: str | None = None,
        limit: int = 100,
    ):
        """
        Fetch orders with optional filters.
        GET /v3/orders
        """
        params = [f"limit={limit}"]
        if status:
            params.append(f"status={status}")
        if created_start_date:
            params.append(f"createdStartDate={created_start_date}")
        if created_end_date:
            params.append(f"createdEndDate={created_end_date}")
        endpoint = f"/v3/orders?{'&'.join(params)}"
        return self.request(method="GET", endpoint=endpoint, db=db)

    def get_order(self, db, purchase_order_id: str):
        """
        Fetch a single order by purchaseOrderId.
        GET /v3/orders/{purchaseOrderId}
        """
        endpoint = f"/v3/orders/{purchase_order_id}"
        return self.request(method="GET", endpoint=endpoint, db=db)

    def acknowledge_order(self, db, purchase_order_id: str):
        """
        Acknowledge a created order.
        POST /v3/orders/{purchaseOrderId}/acknowledge
        """
        endpoint = f"/v3/orders/{purchase_order_id}/acknowledge"
        return self.request(method="POST", endpoint=endpoint, db=db)

    def ship_order(self, db, purchase_order_id: str, order_lines: list[dict]):
        """
        Ship order lines with tracking info.
        POST /v3/orders/{purchaseOrderId}/shipping

        order_lines format:
        [
            {
                "lineNumber": "1",
                "trackingInfo": {
                    "shipDateTime": "1478347200000",
                    "carrierName": "FedEx",
                    "methodCode": "VALUE",
                    "trackingNumber": "TRACK123",
                    "trackingURL": "https://..."
                }
            }
        ]
        """
        endpoint = f"/v3/orders/{purchase_order_id}/shipping"
        payload = {"orderLines": order_lines}
        return self.request(method="POST", endpoint=endpoint, db=db, json=payload)

    def cancel_order(self, db, purchase_order_id: str, order_lines: list[dict]):
        """
        Cancel order lines.
        POST /v3/orders/{purchaseOrderId}/cancel

        order_lines format:
        [
            {
                "orderLineStatuses": {
                    "orderLineStatus": [
                        {
                            "status": "Cancelled",
                            "cancellationReason": "SELLER_CANCEL_OUT_OF_STOCK",
                            "statusQuantity": {"unitOfMeasurement": "EACH"}
                        }
                    ]
                }
            }
        ]
        """
        endpoint = f"/v3/orders/{purchase_order_id}/cancel"
        payload = {"orderCancellation": {"orderLines": {"orderLine": order_lines}}}
        return self.request(method="POST", endpoint=endpoint, db=db, json=payload)

    def refund_order(self, db, purchase_order_id: str, refund_payload: dict):
        """
        Refund order lines.
        POST /v3/orders/{purchaseOrderId}/refund
        """
        endpoint = f"/v3/orders/{purchase_order_id}/refund"
        return self.request(method="POST", endpoint=endpoint, db=db, json=refund_payload)

    # ========================
    # SHIPPING LABELS (Ship With Walmart)
    # ========================

    def walmart_supported_carriers(self, db):
        """
        Fetch supported carriers for shipping labels.
        GET /v3/shipping/labels/carriers
        """
        endpoint = "/v3/shipping/labels/carriers"
        return self.request(method="GET", endpoint=endpoint, db=db)
    
    def get_carrier_package_types(self, db, carrier_short_name: str):
        """
        Fetch supported package types for a carrier.
        GET /v3/shipping/labels/carriers/{carrierShortName}/package-types
        """
        endpoint = f"/v3/shipping/labels/carriers/{carrier_short_name}/package-types"
        return self.request(method="GET", endpoint=endpoint, db=db)

    def request_raw(self, method, endpoint, db, **kwargs):
        """
        Like request(), but returns the raw httpx.Response instead of .json().
        Used for binary downloads (PDF labels).
        """
        self._refresh_token_if_needed(db)

        url = f"{self.base_url}{endpoint}"

        response = httpx.request(
            method,
            url,
            headers=self._get_headers(),
            timeout=30.0,
            **kwargs,
        )

        if response.status_code >= 400:
            raise Exception(f"Walmart API error: {response.text}")

        return response

    def create_shipping_label(self, db, purchase_order_id: str, label_request: dict):
        """
        Create a shipping label for an order.
        POST /v3/shipping/labels

        label_request format:
        label_payload = {
                "boxDimensions": DEFAULT_BOX,
                "fromAddress": FROM_ADDRESS,
                "returnAddress": FROM_ADDRESS,
                "packageType": "CUSTOM_PACKAGE",
                "boxItems": [{"sku": sku, "quantity": 1, "lineNumber": str(line_num)}],
                "purchaseOrderId": po_id,
                "carrierName": CARRIER,
                "carrierServiceType": SERVICE_TYPE,
                "hasBattery": False,
                "hazmat": False
            }
        """
        payload = {
            "boxDimensions": label_request.get("boxDimensions", DEFAULT_BOX),
            "fromAddress": label_request["fromAddress"],
            "returnAddress": label_request["returnAddress"],
            "packageType": label_request.get("packageType", "CUSTOM_PACKAGE"),
            "boxItems": label_request["boxItems"],
            "purchaseOrderId": purchase_order_id,
            "carrierName": label_request["carrierName"],
            "carrierServiceType": label_request["carrierServiceType"],
            "hasBattery": label_request.get("hasBattery", False),
            "hazmat": label_request.get("hazmat", False),
        }
        endpoint = "/v3/shipping/labels"
        result = self.request(method="POST", endpoint=endpoint, db=db, json=payload)
        label_data = result.get("data", result)
        tracking = label_data.get("trackingNo", "N/A")
        carrier_full = label_data.get("carrierFullName", "N/A")
        service = label_data.get("carrierServiceType", "N/A")
        tracking_url = label_data.get("trackingUrl", "N/A")
        return {
            "tracking": tracking,
            "carrier": carrier_full,
            "service": service,
            "tracking_url": tracking_url,
        }

    def get_shipping_label(self, db, purchase_order_id: str):
        """
        Get label details for a purchase order.
        GET /v3/shipping/labels/purchase-orders/{purchaseOrderId}
        """
        endpoint = f"/v3/shipping/labels/purchase-orders/{purchase_order_id}"
        return self.request(method="GET", endpoint=endpoint, db=db)

    def download_shipping_label(self, db, carrier_short_name: str, tracking_no: str) -> bytes:
        """
        Download the shipping label PDF.
        GET /v3/shipping/labels/carriers/{carrierShortName}/trackings/{trackingNo}

        Returns raw PDF bytes.
        """
        endpoint = f"/v3/shipping/labels/carriers/{carrier_short_name}/trackings/{tracking_no}"
        self._refresh_token_if_needed(db)

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        headers["Accept"] = "application/pdf"

        response = httpx.get(url, headers=headers, timeout=30.0)

        if response.status_code >= 400:
            raise Exception(f"Walmart label download error: {response.text}")

        return response.content

    def void_shipping_label(self, db, carrier_short_name: str, tracking_no: str):
        """
        Void/cancel a shipping label.
        DELETE /v3/shipping/labels/carriers/{carrierShortName}/trackings/{trackingNo}
        """
        endpoint = f"/v3/shipping/labels/carriers/{carrier_short_name}/trackings/{tracking_no}"
        return self.request(method="DELETE", endpoint=endpoint, db=db)

    # ========================
    # REPORT MANAGEMENT
    # ========================

    def get_available_report_types(self):
        """
        Get list of supported Walmart report types.
        Based on Walmart API documentation.
        """
        return [
            {"type": "ITEM", "name": "Item Report", "versions": ["v1", "v2", "v3", "v4", "v5"]},
            {"type": "INVENTORY", "name": "Inventory Report", "versions": ["v1"]},
            {"type": "ORDER", "name": "Order Report", "versions": ["v1"]},
            {"type": "RETURN", "name": "Return Report", "versions": ["v1"]},
            {"type": "PERFORMANCE", "name": "Performance Report", "versions": ["v1"]},
            {"type": "PROMOTION", "name": "Promotion Report", "versions": ["v1"]},
        ]

    def create_report_request(self, db, report_type: str, report_version: str, data_start_time: datetime, data_end_time: datetime, row_filters=None, exclude_columns=None):
        """
        Create a Walmart report request.
        POST /v3/reports/reportRequests

        Payload example:
        {
            "reportType": "ITEM",
            "reportVersion": "v1",
            "dataStartTime": "2023-01-01T00:00:00Z",
            "dataEndTime": "2023-01-31T23:59:59Z",
            "rowFilters": {...},
            "excludeColumns": [...]
        }
        """
        payload = {
            "reportType": report_type,
            "reportVersion": report_version,
            "dataStartTime": data_start_time.isoformat().replace('+00:00', 'Z'),
            "dataEndTime": data_end_time.isoformat().replace('+00:00', 'Z'),
        }

        if row_filters:
            payload["rowFilters"] = row_filters
        if exclude_columns:
            payload["excludeColumns"] = exclude_columns

        endpoint = "/v3/reports/reportRequests"
        return self.request(method="POST", endpoint=endpoint, db=db, json=payload)

    def get_report_status(self, db, request_id: str):
        """
        Get the status of a report request.
        GET /v3/reports/reportRequests/{requestId}
        """
        endpoint = f"/v3/reports/reportRequests/{request_id}"
        return self.request(method="GET", endpoint=endpoint, db=db)

    def get_report_download_url(self, db, request_id: str):
        """
        Get the download URL for a completed report.
        GET /v3/reports/downloadReport?requestId={requestId}
        """
        endpoint = f"/v3/reports/downloadReport?requestId={request_id}"
        return self.request(method="GET", endpoint=endpoint, db=db)

    def download_report(self, db, download_url: str) -> bytes:
        """
        Download the report file from the provided URL.
        This is a direct download, not through the Walmart API proxy.
        """
        self._refresh_token_if_needed(db)

        headers = self._get_headers()
        headers["Accept"] = "*/*"  # Accept any content type

        response = httpx.get(download_url, headers=headers, timeout=60.0)

        if response.status_code >= 400:
            raise Exception(f"Report download failed: {response.text}")

        return response.content
