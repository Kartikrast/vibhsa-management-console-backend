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
        Fetch released orders from Walmart and normalize into a common format.
        Returns a list of normalized order dicts.
        """
        limit = kwargs.get("limit", 100)
        response = self.client.get_released_orders(db=db, limit=limit)

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
                    tax_obj = charge.get("tax", {}).get("taxAmount", {})
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
