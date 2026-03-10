import httpx
import uuid
import base64
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings

settings = get_settings()

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

    def _get_headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "WM_SVC.NAME": "Vibhsa",
            "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
            "WM_CONSUMER.CHANNEL.TYPE": self.account.seller_id,  # from Walmart portal
            "WM_SEC.ACCESS_TOKEN": self.account.access_token,
        }

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

    def request(self, method, endpoint, db, **kwargs):
        """
        Centralized request method
        """
        self._refresh_token_if_needed(db)

        url = f"{self.base_url}{endpoint}"

        response = httpx.request(
            method,
            url,
            headers=self._get_headers(),
            **kwargs,
        )

        if response.status_code >= 400:
            raise Exception(f"Walmart API error: {response.text}")

        return response.json()

    def get_items(self, db, limit: int = 10):
        """
        Fetch product listings from Walmart.
        """
        endpoint = f"/v3/items?limit={limit}"

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
        {
            "packageType": "CUSTOM_PACKAGE",
            "boxDimensions": {
                "boxDimensionUnit": "IN",
                "boxWeightUnit": "LB",
                "boxWeight": 1,
                "boxLength": 10,
                "boxWidth": 8,
                "boxHeight": 4,
            },
            "boxItems": [
                {
                    "sku": "SKU123",
                    "quantity": 1,
                    "countryOfOrigin": "US",
                    "harmonizedCode": "",
                }
            ],
            "fromAddress": {
                "contactName": "Seller Name",
                "companyName": "Company",
                "addressLine1": "123 Main St",
                "city": "City",
                "state": "CA",
                "postalCode": "90001",
                "country": "US",
                "phone": "5551234567",
            },
        }
        """
        payload = {
            "purchaseOrderId": purchase_order_id,
            **label_request,
        }
        endpoint = "/v3/shipping/labels"
        return self.request(method="POST", endpoint=endpoint, db=db, json=payload)

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

        response = httpx.get(url, headers=headers)

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
