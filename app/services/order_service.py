"""
Marketplace-agnostic order action service.
Each action: validate → update local DB → call marketplace adapter → inventory hook → audit log.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.marketplaces.adapter_registry import get_order_adapter
from app.models.order import Order, OrderLine, OrderStatusLog, OrderStatus, OrderLineStatus
from app.models.marketplace_account import MarketplaceAccount
from app.services.inventory_service import reserve_inventory, deduct_inventory, release_reservation

logger = logging.getLogger(__name__)


def _get_order_for_org(db: Session, org_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    """Fetch an order belonging to the given organization or raise 404."""
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.organization_id == org_id)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order


def _get_marketplace_account(db: Session, account_id: uuid.UUID) -> MarketplaceAccount:
    """Fetch marketplace account or raise 404."""
    account = db.get(MarketplaceAccount, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marketplace account not found",
        )
    return account


def _log_status(
    db: Session,
    order_id: uuid.UUID,
    order_line_id: uuid.UUID | None,
    old_status: str | None,
    new_status: str,
    source: str = "USER",
    details: dict | None = None,
):
    db.add(OrderStatusLog(
        order_id=order_id,
        order_line_id=order_line_id,
        previous_status=old_status,
        new_status=new_status,
        source=source,
        details=details,
    ))


# ========================
# ACKNOWLEDGE
# ========================

def acknowledge_order(
    db: Session,
    org_id: uuid.UUID,
    order_id: uuid.UUID,
) -> Order:
    """
    Acknowledge a CREATED order.
    1. Validate status
    2. Call marketplace adapter
    3. Update local status
    4. Reserve inventory for linked lines
    5. Audit log
    """
    order = _get_order_for_org(db, org_id, order_id)

    if order.status != OrderStatus.CREATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot acknowledge order in {order.status.value} status",
        )

    account = _get_marketplace_account(db, order.marketplace_account_id)
    adapter = get_order_adapter(order.marketplace, account)

    # Call marketplace
    line_numbers = [
        {"line_number": line.line_number}
        for line in order.lines
        if line.status == OrderLineStatus.CREATED
    ]
    adapter.acknowledge_order(db=db, external_order_id=order.external_order_id, lines=line_numbers)

    # Update local state
    old_order_status = order.status
    order.status = OrderStatus.ACKNOWLEDGED

    for line in order.lines:
        if line.status == OrderLineStatus.CREATED:
            old_line_status = line.status
            line.status = OrderLineStatus.ACKNOWLEDGED

            _log_status(
                db, order.id, line.id,
                old_line_status.value, OrderLineStatus.ACKNOWLEDGED.value,
            )

            # Inventory reservation
            if line.product_variant_id:
                reserve_inventory(db, org_id, line.product_variant_id, line.quantity)

    _log_status(
        db, order.id, None,
        old_order_status.value, OrderStatus.ACKNOWLEDGED.value,
    )

    db.commit()
    return order


# ========================
# SHIP
# ========================

def ship_order_lines(
    db: Session,
    org_id: uuid.UUID,
    order_id: uuid.UUID,
    shipment_lines: list[dict],
) -> Order:
    """
    Ship order lines with tracking info.

    shipment_lines format:
    [
        {
            "line_id": UUID,
            "carrier": "FedEx",
            "tracking_number": "TRACK123",
            "tracking_url": "https://...",
        }
    ]
    """
    order = _get_order_for_org(db, org_id, order_id)

    if order.status not in (OrderStatus.ACKNOWLEDGED, OrderStatus.PARTIALLY_SHIPPED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot ship order in {order.status.value} status",
        )

    account = _get_marketplace_account(db, order.marketplace_account_id)
    adapter = get_order_adapter(order.marketplace, account)

    # Build line lookup
    line_map = {line.id: line for line in order.lines}

    adapter_lines = []
    lines_to_update = []

    for sl in shipment_lines:
        line_id = sl["line_id"]
        if isinstance(line_id, str):
            line_id = uuid.UUID(line_id)

        line = line_map.get(line_id)
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order line {line_id} not found",
            )

        if line.status != OrderLineStatus.ACKNOWLEDGED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.line_number} is in {line.status.value} status, cannot ship",
            )

        adapter_lines.append({
            "line_number": line.line_number,
            "carrier": sl.get("carrier", "Other"),
            "tracking_number": sl.get("tracking_number", ""),
            "tracking_url": sl.get("tracking_url", ""),
        })
        lines_to_update.append((line, sl))

    # Call marketplace
    adapter.ship_order(
        db=db,
        external_order_id=order.external_order_id,
        lines=adapter_lines,
    )

    # Update local state
    for line, sl in lines_to_update:
        old_status = line.status
        line.status = OrderLineStatus.SHIPPED
        line.tracking_carrier = sl.get("carrier")
        line.tracking_number = sl.get("tracking_number")
        line.tracking_url = sl.get("tracking_url")
        line.ship_date = datetime.now(timezone.utc)

        _log_status(
            db, order.id, line.id,
            old_status.value, OrderLineStatus.SHIPPED.value,
        )

        # Inventory deduction
        if line.product_variant_id:
            deduct_inventory(db, org_id, line.product_variant_id, line.quantity)

    # Derive header status
    db.flush()
    all_statuses = {l.status for l in order.lines}
    old_order_status = order.status

    if all(s in (OrderLineStatus.SHIPPED, OrderLineStatus.DELIVERED) for s in all_statuses):
        order.status = OrderStatus.SHIPPED
    else:
        order.status = OrderStatus.PARTIALLY_SHIPPED

    if old_order_status != order.status:
        _log_status(
            db, order.id, None,
            old_order_status.value, order.status.value,
        )

    db.commit()
    return order


# ========================
# CANCEL
# ========================

def cancel_order_lines(
    db: Session,
    org_id: uuid.UUID,
    order_id: uuid.UUID,
    cancel_lines: list[dict],
) -> Order:
    """
    Cancel order lines.

    cancel_lines format:
    [
        {
            "line_id": UUID,
            "reason": "SELLER_CANCEL_OUT_OF_STOCK",
        }
    ]
    """
    order = _get_order_for_org(db, org_id, order_id)

    account = _get_marketplace_account(db, order.marketplace_account_id)
    adapter = get_order_adapter(order.marketplace, account)

    line_map = {line.id: line for line in order.lines}

    adapter_lines = []
    lines_to_update = []

    for cl in cancel_lines:
        line_id = cl["line_id"]
        if isinstance(line_id, str):
            line_id = uuid.UUID(line_id)

        line = line_map.get(line_id)
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order line {line_id} not found",
            )

        if line.status not in (OrderLineStatus.CREATED, OrderLineStatus.ACKNOWLEDGED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.line_number} is in {line.status.value} status, cannot cancel",
            )

        adapter_lines.append({
            "line_number": line.line_number,
            "reason": cl.get("reason", "SELLER_CANCEL_OUT_OF_STOCK"),
            "quantity": line.quantity,
        })
        lines_to_update.append((line, cl))

    # Call marketplace
    adapter.cancel_order(
        db=db,
        external_order_id=order.external_order_id,
        lines=adapter_lines,
    )

    # Update local state
    for line, cl in lines_to_update:
        old_status = line.status
        line.status = OrderLineStatus.CANCELLED
        line.cancellation_reason = cl.get("reason", "SELLER_CANCEL_OUT_OF_STOCK")

        _log_status(
            db, order.id, line.id,
            old_status.value, OrderLineStatus.CANCELLED.value,
        )

        # Release reservation if was acknowledged
        if old_status == OrderLineStatus.ACKNOWLEDGED and line.product_variant_id:
            release_reservation(db, org_id, line.product_variant_id, line.quantity)

    # Derive header status
    db.flush()
    all_statuses = {l.status for l in order.lines}
    old_order_status = order.status

    if all(s == OrderLineStatus.CANCELLED for s in all_statuses):
        order.status = OrderStatus.CANCELLED
    # Otherwise keep current status

    if old_order_status != order.status:
        _log_status(
            db, order.id, None,
            old_order_status.value, order.status.value,
        )

    db.commit()
    return order


# ========================
# REFUND
# ========================

def refund_order_lines(
    db: Session,
    org_id: uuid.UUID,
    order_id: uuid.UUID,
    refund_lines: list[dict],
) -> Order:
    """
    Refund order lines.

    refund_lines format:
    [
        {
            "line_id": UUID,
            "amount": 29.99,
        }
    ]
    """
    order = _get_order_for_org(db, org_id, order_id)

    account = _get_marketplace_account(db, order.marketplace_account_id)
    adapter = get_order_adapter(order.marketplace, account)

    line_map = {line.id: line for line in order.lines}

    adapter_lines = []
    lines_to_update = []

    for rl in refund_lines:
        line_id = rl["line_id"]
        if isinstance(line_id, str):
            line_id = uuid.UUID(line_id)

        line = line_map.get(line_id)
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order line {line_id} not found",
            )

        if line.status not in (OrderLineStatus.SHIPPED, OrderLineStatus.DELIVERED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line.line_number} is in {line.status.value} status, cannot refund",
            )

        adapter_lines.append({
            "line_number": line.line_number,
            "amount": rl["amount"],
        })
        lines_to_update.append((line, rl))

    # Call marketplace
    adapter.refund_order(
        db=db,
        external_order_id=order.external_order_id,
        lines=adapter_lines,
    )

    # Update local state
    for line, rl in lines_to_update:
        old_status = line.status
        line.status = OrderLineStatus.REFUNDED
        line.refund_amount = rl["amount"]

        _log_status(
            db, order.id, line.id,
            old_status.value, OrderLineStatus.REFUNDED.value,
        )

    db.commit()
    return order


# ========================
# LINK ORDER LINE
# ========================

def link_order_line_to_variant(
    db: Session,
    org_id: uuid.UUID,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    product_variant_id: uuid.UUID,
) -> OrderLine:
    """Manually link an order line to a product variant."""
    order = _get_order_for_org(db, org_id, order_id)

    line = (
        db.query(OrderLine)
        .filter(OrderLine.id == line_id, OrderLine.order_id == order.id)
        .first()
    )
    if not line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order line not found",
        )

    line.product_variant_id = product_variant_id
    db.commit()
    return line
