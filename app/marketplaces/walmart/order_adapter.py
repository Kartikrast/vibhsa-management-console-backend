from sqlalchemy.orm import Session

from app.marketplaces.base_adapter import MarketplaceOrderAdapter
from app.marketplaces.walmart.client import WalmartClient
from app.models.marketplace_account import MarketplaceAccount


class WalmartOrderAdapter(MarketplaceOrderAdapter):
    """
    Walmart implementation of the marketplace order adapter.
    Translates between the generic adapter interface and WalmartClient API calls.
    """

    def __init__(self, account: MarketplaceAccount):
        self.account = account
        self.client = WalmartClient(account)

    def fetch_new_orders(self, db: Session, **kwargs) -> list[dict]:
        """
        Fetch all orders from Walmart and normalize into a common format.
        Supports optional filters: status, created_start_date, created_end_date, limit.
        Returns a list of normalized order dicts.
        """
        limit = kwargs.get("limit", 100)
        status = kwargs.get("status")
        created_start_date = kwargs.get("created_start_date")
        created_end_date = kwargs.get("created_end_date")

        response = self.client.get_all_orders(
            db=db,
            status=status,
            created_start_date=created_start_date,
            created_end_date=created_end_date,
            limit=limit,
        )

        raw_orders = (
            response.get("list", {})
            .get("elements", {})
            .get("order", [])
        )

        return [self._normalize_order(raw) for raw in raw_orders]

    def fetch_order(self, db: Session, external_order_id: str) -> dict:
        """Fetch a single order and normalize."""
        response = self.client.get_order(db=db, purchase_order_id=external_order_id)
        raw_order = response.get("order", response)
        return self._normalize_order(raw_order)

    def acknowledge_order(self, db: Session, external_order_id: str, lines: list) -> dict:
        """Acknowledge order on Walmart."""
        return self.client.acknowledge_order(db=db, purchase_order_id=external_order_id)

    def ship_order(self, db: Session, external_order_id: str, lines: list) -> dict:
        """
        Ship order lines on Walmart.

        lines format (internal):
        [
            {
                "line_number": "1",
                "carrier": "FedEx",
                "tracking_number": "TRACK123",
                "tracking_url": "https://...",
                "method_code": "VALUE",
            }
        ]
        """
        walmart_lines = []
        for line in lines:
            walmart_lines.append({
                "lineNumber": line["line_number"],
                "trackingInfo": {
                    "shipDateTime": str(int(__import__("time").time() * 1000)),
                    "carrierName": line.get("carrier", "Other"),
                    "methodCode": line.get("method_code", "VALUE"),
                    "trackingNumber": line.get("tracking_number", ""),
                    "trackingURL": line.get("tracking_url", ""),
                },
            })

        return self.client.ship_order(
            db=db,
            purchase_order_id=external_order_id,
            order_lines=walmart_lines,
        )

    def cancel_order(self, db: Session, external_order_id: str, lines: list) -> dict:
        """
        Cancel order lines on Walmart.

        lines format (internal):
        [
            {
                "line_number": "1",
                "reason": "SELLER_CANCEL_OUT_OF_STOCK",
                "quantity": 1,
            }
        ]
        """
        walmart_lines = []
        for line in lines:
            walmart_lines.append({
                "lineNumber": line["line_number"],
                "orderLineStatuses": {
                    "orderLineStatus": [
                        {
                            "status": "Cancelled",
                            "cancellationReason": line.get(
                                "reason", "SELLER_CANCEL_OUT_OF_STOCK"
                            ),
                            "statusQuantity": {
                                "unitOfMeasurement": "EACH",
                                "amount": str(line.get("quantity", 1)),
                            },
                        }
                    ]
                },
            })

        return self.client.cancel_order(
            db=db,
            purchase_order_id=external_order_id,
            order_lines=walmart_lines,
        )

    def refund_order(self, db: Session, external_order_id: str, lines: list) -> dict:
        """
        Refund order lines on Walmart.

        lines format (internal):
        [
            {
                "line_number": "1",
                "amount": 29.99,
            }
        ]
        """
        walmart_lines = []
        for line in lines:
            walmart_lines.append({
                "lineNumber": line["line_number"],
                "refund": {
                    "refundCharges": {
                        "refundCharge": [
                            {
                                "chargeType": "PRODUCT",
                                "chargeName": "ItemPrice",
                                "chargeAmount": {
                                    "currency": "USD",
                                    "amount": line["amount"],
                                },
                            }
                        ]
                    }
                },
            })

        payload = {
            "orderRefund": {
                "purchaseOrderId": external_order_id,
                "orderLines": {"orderLine": walmart_lines},
            }
        }

        return self.client.refund_order(
            db=db,
            purchase_order_id=external_order_id,
            refund_payload=payload,
        )

    # ========================
    # SHIPPING LABELS
    # ========================

    def create_shipping_label(self, db: Session, external_order_id: str, label_data: dict) -> dict:
        """
        Create a shipping label via Ship With Walmart.

        label_data format (internal):
        {
            "package_type": "CUSTOM_PACKAGE",
            "box_weight": 16,
            "box_length": 6,
            "box_width": 6,
            "box_height": 4,
            "box_dimension_unit": "IN",
            "box_weight_unit": "OZ",
            "box_items": [
                {"sku": "SKU123", "quantity": 1, "line_number": "1"}
            ],
            "from_address": { ... },
            "return_address": { ... },
            "carrier_name": "USPS",
            "carrier_service_type": "GROUND_ADVANTAGE",
            "has_battery": False,
            "hazmat": False,
        }
        """
        walmart_box_items = []
        for item in label_data.get("box_items", []):
            box_item = {
                "sku": item["sku"],
                "quantity": item.get("quantity", 1),
            }
            if item.get("line_number"):
                box_item["lineNumber"] = str(item["line_number"])
            walmart_box_items.append(box_item)

        def _build_address(addr: dict) -> dict:
            return {
                "contactName": addr.get("contact_name", ""),
                "companyName": addr.get("company_name", ""),
                "addressLine1": addr.get("address_line1", ""),
                "addressLine2": addr.get("address_line2", ""),
                "city": addr.get("city", ""),
                "state": addr.get("state", ""),
                "postalCode": addr.get("postal_code", ""),
                "country": addr.get("country", "US"),
                "phone": addr.get("phone", ""),
            }

        from_addr = label_data.get("from_address", {})
        return_addr = label_data.get("return_address") or from_addr

        walmart_request = {
            "packageType": label_data.get("package_type", "CUSTOM_PACKAGE"),
            "boxDimensions": {
                "boxDimensionUnit": label_data.get("box_dimension_unit", "IN"),
                "boxWeightUnit": label_data.get("box_weight_unit", "OZ"),
                "boxWeight": label_data.get("box_weight", 16),
                "boxLength": label_data.get("box_length", 6),
                "boxWidth": label_data.get("box_width", 6),
                "boxHeight": label_data.get("box_height", 4),
            },
            "boxItems": walmart_box_items,
            "fromAddress": _build_address(from_addr),
            "returnAddress": _build_address(return_addr),
            "carrierName": label_data.get("carrier_name", "USPS"),
            "carrierServiceType": label_data.get("carrier_service_type", "GROUND_ADVANTAGE"),
            "hasBattery": label_data.get("has_battery", False),
            "hazmat": label_data.get("hazmat", False),
        }

        return self.client.create_shipping_label(
            db=db,
            purchase_order_id=external_order_id,
            label_request=walmart_request,
        )

    def get_shipping_label(self, db: Session, external_order_id: str) -> dict:
        """Get label details for a purchase order."""
        return self.client.get_shipping_label(
            db=db,
            purchase_order_id=external_order_id,
        )

    def download_shipping_label(self, db: Session, carrier: str, tracking_number: str) -> bytes:
        """Download the label PDF as raw bytes."""
        return self.client.download_shipping_label(
            db=db,
            carrier_short_name=carrier,
            tracking_no=tracking_number,
        )

    def void_shipping_label(self, db: Session, carrier: str, tracking_number: str) -> dict:
        """Void a shipping label."""
        return self.client.void_shipping_label(
            db=db,
            carrier_short_name=carrier,
            tracking_no=tracking_number,
        )

    # ========================
    # NORMALIZATION
    # ========================

    @staticmethod
    def _normalize_order(raw: dict) -> dict:
        """
        Normalize a Walmart order response into a common dict format
        consumed by the order import service.
        """
        def _num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                try:
                    return float(str(v))
                except Exception:
                    return 0.0

        shipping_info = raw.get("shippingInfo", {})
        postal = shipping_info.get("postalAddress", {})

        order_lines_raw = (
            raw.get("orderLines", {}).get("orderLine", [])
        )

        lines = []
        for ol in order_lines_raw:
            item = ol.get("item", {})
            charges = ol.get("charges", {}).get("charge", [])

            unit_price = 0.0
            shipping_charge = 0.0
            tax_amount = 0.0

            for charge in charges:
                amount = _num(charge.get("chargeAmount", {}).get("amount", 0))
                charge_type = charge.get("chargeType", "")

                if charge_type == "PRODUCT":
                    unit_price = amount
                    tax_obj = (charge.get("tax") or {}).get("taxAmount") or {}
                    tax_amount += _num(tax_obj.get("amount", 0))
                elif charge_type == "SHIPPING":
                    shipping_charge = amount

            qty_info = ol.get("orderLineQuantity", {})
            try:
                quantity = int(float(qty_info.get("amount", 1) or 1))
            except (TypeError, ValueError):
                quantity = 1

            statuses = (
                ol.get("orderLineStatuses", {})
                .get("orderLineStatus", [])
            )
            line_status = statuses[0].get("status", "Created") if statuses else "Created"

            lines.append({
                "line_number": ol.get("lineNumber", ""),
                "external_sku": item.get("sku", ""),
                "product_name": item.get("productName", ""),
                "quantity": quantity,
                "unit_price": unit_price,
                "shipping_charge": shipping_charge,
                "tax_amount": tax_amount,
                "status": line_status,
                "raw": ol,
            })

        return {
            "external_order_id": raw.get("purchaseOrderId", ""),
            "customer_order_id": raw.get("customerOrderId", ""),
            "order_type": raw.get("orderType", "REGULAR"),
            "order_date_ms": raw.get("orderDate"),
            "customer_name": postal.get("name", ""),
            "customer_email": raw.get("customerEmailId", ""),
            "customer_phone": shipping_info.get("phone", ""),
            "shipping_address": {
                "name": postal.get("name", ""),
                "address1": postal.get("address1", ""),
                "address2": postal.get("address2", ""),
                "city": postal.get("city", ""),
                "state": postal.get("state", ""),
                "postalCode": postal.get("postalCode", ""),
                "country": postal.get("country", ""),
                "addressType": postal.get("addressType", ""),
            },
            "shipping_method": shipping_info.get("methodCode", ""),
            "estimated_ship_date_ms": shipping_info.get("estimatedShipDate"),
            "estimated_delivery_date_ms": shipping_info.get("estimatedDeliveryDate"),
            "currency": "USD",
            "lines": lines,
            "raw": raw,
        }
