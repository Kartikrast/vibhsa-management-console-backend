"""
Marketplace-agnostic order import service.
Takes normalized order dicts (from any adapter) and upserts them into the canonical Order/OrderLine models.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.marketplaces.adapter_registry import get_order_adapter
from app.models.order import Order, OrderLine, OrderStatusLog, OrderStatus, OrderLineStatus
from app.models.marketplace_account import MarketplaceAccount
from app.models.marketplace_listing import MarketplaceListing

logger = logging.getLogger(__name__)


# ========================
# STATUS MAPPING
# ========================

MARKETPLACE_STATUS_MAP = {
    "Created": OrderLineStatus.CREATED,
    "Acknowledged": OrderLineStatus.ACKNOWLEDGED,
    "Shipped": OrderLineStatus.SHIPPED,
    "Delivered": OrderLineStatus.DELIVERED,
    "Cancelled": OrderLineStatus.CANCELLED,
}


def _ms_to_datetime(ms_value) -> datetime | None:
    """Convert a millisecond timestamp (int or str) to a timezone-aware datetime."""
    if ms_value is None:
        return None
    try:
        return datetime.fromtimestamp(int(ms_value) / 1000, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _resolve_variant_id(db: Session, organization_id, external_sku: str):
    """
    Attempt to auto-link an order line SKU to an internal product variant
    via MarketplaceListing.marketplace_sku → product_variant_id.
    """
    if not external_sku:
        return None

    listing = (
        db.query(MarketplaceListing)
        .filter(
            MarketplaceListing.organization_id == organization_id,
            MarketplaceListing.marketplace_sku == external_sku,
            MarketplaceListing.product_variant_id.isnot(None),
        )
        .first()
    )

    return listing.product_variant_id if listing else None


def _derive_order_status(lines: list[OrderLine]) -> OrderStatus:
    """Derive the header-level order status from the statuses of all lines."""
    statuses = {line.status for line in lines}

    if all(s == OrderLineStatus.CANCELLED for s in statuses):
        return OrderStatus.CANCELLED
    if all(s == OrderLineStatus.DELIVERED for s in statuses):
        return OrderStatus.DELIVERED
    if all(s in (OrderLineStatus.SHIPPED, OrderLineStatus.DELIVERED) for s in statuses):
        return OrderStatus.SHIPPED
    if OrderLineStatus.SHIPPED in statuses:
        return OrderStatus.PARTIALLY_SHIPPED
    if all(s == OrderLineStatus.ACKNOWLEDGED for s in statuses):
        return OrderStatus.ACKNOWLEDGED
    return OrderStatus.CREATED


def import_orders(
    db: Session,
    organization_id,
    marketplace_account: MarketplaceAccount,
) -> dict:
    """
    Import orders from a marketplace account into the canonical order tables.

    1. Resolve the adapter for the marketplace.
    2. Fetch normalized orders.
    3. Upsert Order + OrderLine rows.
    4. Auto-link SKUs to product variants.
    5. Log status changes.

    Returns: {"imported": int, "updated": int, "skipped": int}
    """
    adapter = get_order_adapter(marketplace_account.marketplace, marketplace_account)
    normalized_orders = adapter.fetch_new_orders(db=db)

    imported_count = 0
    updated_count = 0
    skipped_count = 0

    for norm in normalized_orders:
        external_order_id = norm.get("external_order_id")
        if not external_order_id:
            skipped_count += 1
            continue

        try:
            _upsert_order(
                db=db,
                organization_id=organization_id,
                marketplace_account=marketplace_account,
                normalized=norm,
            )

            # Check if this was an insert or update
            existing = (
                db.query(Order)
                .filter(
                    Order.organization_id == organization_id,
                    Order.marketplace == marketplace_account.marketplace,
                    Order.external_order_id == external_order_id,
                )
                .first()
            )

            if existing and existing.created_at == existing.updated_at:
                imported_count += 1
            else:
                updated_count += 1

        except Exception:
            logger.exception(
                "Failed to import order %s", external_order_id
            )
            skipped_count += 1

    db.commit()

    return {
        "imported": imported_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "message": "Order import completed",
    }


def _upsert_order(
    db: Session,
    organization_id,
    marketplace_account: MarketplaceAccount,
    normalized: dict,
):
    """Upsert a single order and its lines from a normalized dict."""

    external_order_id = normalized["external_order_id"]
    marketplace = marketplace_account.marketplace

    existing_order = (
        db.query(Order)
        .filter(
            Order.organization_id == organization_id,
            Order.marketplace == marketplace,
            Order.external_order_id == external_order_id,
        )
        .first()
    )

    order_date = _ms_to_datetime(normalized.get("order_date_ms"))
    est_ship = _ms_to_datetime(normalized.get("estimated_ship_date_ms"))
    est_delivery = _ms_to_datetime(normalized.get("estimated_delivery_date_ms"))

    # Calculate order total from lines
    lines_data = normalized.get("lines", [])
    order_total = sum(
        (l.get("unit_price", 0) or 0) * (l.get("quantity", 1) or 1)
        + (l.get("shipping_charge", 0) or 0)
        + (l.get("tax_amount", 0) or 0)
        for l in lines_data
    )

    if existing_order:
        # UPDATE
        existing_order.customer_order_id = normalized.get("customer_order_id")
        existing_order.order_type = normalized.get("order_type")
        existing_order.customer_name = normalized.get("customer_name")
        existing_order.customer_email = normalized.get("customer_email")
        existing_order.customer_phone = normalized.get("customer_phone")
        existing_order.shipping_address = normalized.get("shipping_address")
        existing_order.shipping_method = normalized.get("shipping_method")
        existing_order.estimated_ship_date = est_ship
        existing_order.estimated_delivery_date = est_delivery
        existing_order.order_date = order_date
        existing_order.order_total = Decimal(str(order_total)) if order_total else None
        existing_order.currency = normalized.get("currency", "USD")
        existing_order.raw_payload = normalized.get("raw")
        existing_order.last_synced_at = datetime.now(timezone.utc)

        order = existing_order
    else:
        # INSERT
        order = Order(
            organization_id=organization_id,
            marketplace_account_id=marketplace_account.id,
            marketplace=marketplace,
            external_order_id=external_order_id,
            customer_order_id=normalized.get("customer_order_id"),
            order_type=normalized.get("order_type"),
            status=OrderStatus.CREATED,
            customer_name=normalized.get("customer_name"),
            customer_email=normalized.get("customer_email"),
            customer_phone=normalized.get("customer_phone"),
            shipping_address=normalized.get("shipping_address"),
            shipping_method=normalized.get("shipping_method"),
            estimated_ship_date=est_ship,
            estimated_delivery_date=est_delivery,
            order_date=order_date,
            order_total=Decimal(str(order_total)) if order_total else None,
            currency=normalized.get("currency", "USD"),
            raw_payload=normalized.get("raw"),
            last_synced_at=datetime.now(timezone.utc),
        )
        db.add(order)
        db.flush()

    # Upsert lines
    for line_data in lines_data:
        _upsert_order_line(db, order, organization_id, line_data)

    # Derive header status from line statuses
    db.flush()
    all_lines = (
        db.query(OrderLine)
        .filter(OrderLine.order_id == order.id)
        .all()
    )
    new_status = _derive_order_status(all_lines)

    if order.status != new_status:
        old_status = order.status
        order.status = new_status
        db.add(OrderStatusLog(
            order_id=order.id,
            previous_status=old_status.value if old_status else None,
            new_status=new_status.value,
            source="MARKETPLACE_SYNC",
            details={"external_order_id": external_order_id},
        ))


def _upsert_order_line(
    db: Session,
    order: Order,
    organization_id,
    line_data: dict,
):
    """Upsert a single order line."""

    line_number = str(line_data.get("line_number", ""))

    existing_line = (
        db.query(OrderLine)
        .filter(
            OrderLine.order_id == order.id,
            OrderLine.line_number == line_number,
        )
        .first()
    )

    marketplace_status = line_data.get("status", "Created")
    mapped_status = MARKETPLACE_STATUS_MAP.get(marketplace_status, OrderLineStatus.CREATED)

    variant_id = _resolve_variant_id(
        db, organization_id, line_data.get("external_sku")
    )

    if existing_line:
        old_status = existing_line.status

        existing_line.external_sku = line_data.get("external_sku")
        existing_line.product_name = line_data.get("product_name")
        existing_line.quantity = line_data.get("quantity", 1)
        existing_line.unit_price = (
            Decimal(str(line_data["unit_price"])) if line_data.get("unit_price") else None
        )
        existing_line.shipping_charge = (
            Decimal(str(line_data["shipping_charge"])) if line_data.get("shipping_charge") else None
        )
        existing_line.tax_amount = (
            Decimal(str(line_data["tax_amount"])) if line_data.get("tax_amount") else None
        )
        existing_line.status = mapped_status
        existing_line.raw_line_payload = line_data.get("raw")

        if variant_id and not existing_line.product_variant_id:
            existing_line.product_variant_id = variant_id

        if old_status != mapped_status:
            db.add(OrderStatusLog(
                order_id=order.id,
                order_line_id=existing_line.id,
                previous_status=old_status.value,
                new_status=mapped_status.value,
                source="MARKETPLACE_SYNC",
                details={"line_number": line_number},
            ))
    else:
        new_line = OrderLine(
            order_id=order.id,
            organization_id=organization_id,
            line_number=line_number,
            external_sku=line_data.get("external_sku"),
            product_name=line_data.get("product_name"),
            product_variant_id=variant_id,
            quantity=line_data.get("quantity", 1),
            unit_price=(
                Decimal(str(line_data["unit_price"])) if line_data.get("unit_price") else None
            ),
            shipping_charge=(
                Decimal(str(line_data["shipping_charge"])) if line_data.get("shipping_charge") else None
            ),
            tax_amount=(
                Decimal(str(line_data["tax_amount"])) if line_data.get("tax_amount") else None
            ),
            status=mapped_status,
            raw_line_payload=line_data.get("raw"),
        )
        db.add(new_line)
        db.flush()

        db.add(OrderStatusLog(
            order_id=order.id,
            order_line_id=new_line.id,
            previous_status=None,
            new_status=mapped_status.value,
            source="MARKETPLACE_SYNC",
            details={"line_number": line_number},
        ))
