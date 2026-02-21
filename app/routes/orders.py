from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_context
from app.models.order import Order, OrderLine, OrderStatusLog
from app.models.marketplace_account import MarketplaceAccount
from app.schemas.order import (
    OrderListResponse,
    OrderDetailResponse,
    OrderLineResponse,
    OrderStatusLogResponse,
    OrderImportResponse,
    ShipOrderRequest,
    CancelOrderRequest,
    RefundOrderRequest,
    LinkOrderLineRequest,
)
from app.services.order_service import (
    acknowledge_order,
    ship_order_lines,
    cancel_order_lines,
    refund_order_lines,
    link_order_line_to_variant,
)
from app.services.order_import.order_import_service import import_orders

router = APIRouter(prefix="/orders", tags=["Orders"])


# ========================
# IMPORT
# ========================

@router.post("/import", response_model=OrderImportResponse)
def import_orders_route(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Trigger order import from all connected marketplace accounts."""
    organization = context["organization"]

    accounts = (
        db.query(MarketplaceAccount)
        .filter(
            MarketplaceAccount.organization_id == organization.id,
            MarketplaceAccount.is_active.is_(True),
        )
        .all()
    )

    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active marketplace accounts found",
        )

    total_imported = 0
    total_updated = 0
    total_skipped = 0

    for account in accounts:
        result = import_orders(
            db=db,
            organization_id=organization.id,
            marketplace_account=account,
        )
        total_imported += result["imported"]
        total_updated += result["updated"]
        total_skipped += result["skipped"]

    return OrderImportResponse(
        imported=total_imported,
        updated=total_updated,
        skipped=total_skipped,
        message="Order import completed",
    )


# ========================
# LIST / DETAIL
# ========================

@router.get("/", response_model=list[OrderListResponse])
def list_orders(
    status_filter: str | None = Query(None, alias="status"),
    marketplace: str | None = None,
    page: int = 1,
    page_size: int = 20,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """List orders with optional filters."""
    organization = context["organization"]

    query = db.query(Order).filter(
        Order.organization_id == organization.id
    )

    if status_filter:
        query = query.filter(Order.status == status_filter)
    if marketplace:
        query = query.filter(Order.marketplace == marketplace)

    orders = (
        query
        .order_by(Order.order_date.desc().nullslast(), Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return orders


@router.get("/{order_id}", response_model=OrderDetailResponse)
def get_order_detail(
    order_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get full order detail with lines."""
    organization = context["organization"]

    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.organization_id == organization.id,
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order


# ========================
# ACTIONS
# ========================

@router.post("/{order_id}/acknowledge", response_model=OrderDetailResponse)
def acknowledge_order_route(
    order_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Acknowledge a created order and push to marketplace."""
    organization = context["organization"]
    order = acknowledge_order(db=db, org_id=organization.id, order_id=order_id)
    return order


@router.post("/{order_id}/ship", response_model=OrderDetailResponse)
def ship_order_route(
    order_id: UUID,
    payload: ShipOrderRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Ship order lines with tracking info."""
    organization = context["organization"]

    shipment_lines = [
        {
            "line_id": line.line_id,
            "carrier": line.carrier,
            "tracking_number": line.tracking_number,
            "tracking_url": line.tracking_url,
        }
        for line in payload.lines
    ]

    order = ship_order_lines(
        db=db,
        org_id=organization.id,
        order_id=order_id,
        shipment_lines=shipment_lines,
    )
    return order


@router.post("/{order_id}/cancel", response_model=OrderDetailResponse)
def cancel_order_route(
    order_id: UUID,
    payload: CancelOrderRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Cancel order lines."""
    organization = context["organization"]

    cancel_data = [
        {
            "line_id": line.line_id,
            "reason": line.reason,
        }
        for line in payload.lines
    ]

    order = cancel_order_lines(
        db=db,
        org_id=organization.id,
        order_id=order_id,
        cancel_lines=cancel_data,
    )
    return order


@router.post("/{order_id}/refund", response_model=OrderDetailResponse)
def refund_order_route(
    order_id: UUID,
    payload: RefundOrderRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Refund order lines."""
    organization = context["organization"]

    refund_data = [
        {
            "line_id": line.line_id,
            "amount": line.amount,
        }
        for line in payload.lines
    ]

    order = refund_order_lines(
        db=db,
        org_id=organization.id,
        order_id=order_id,
        refund_lines=refund_data,
    )
    return order


# ========================
# LINK LINE TO VARIANT
# ========================

@router.post(
    "/{order_id}/lines/{line_id}/link",
    response_model=OrderLineResponse,
)
def link_order_line_route(
    order_id: UUID,
    line_id: UUID,
    payload: LinkOrderLineRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Manually link an order line to an internal product variant."""
    organization = context["organization"]

    line = link_order_line_to_variant(
        db=db,
        org_id=organization.id,
        order_id=order_id,
        line_id=line_id,
        product_variant_id=payload.product_variant_id,
    )
    return line


# ========================
# AUDIT LOG
# ========================

@router.get(
    "/{order_id}/logs",
    response_model=list[OrderStatusLogResponse],
)
def get_order_logs(
    order_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get the status change audit trail for an order."""
    organization = context["organization"]

    # Verify order belongs to org
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.organization_id == organization.id,
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    logs = (
        db.query(OrderStatusLog)
        .filter(OrderStatusLog.order_id == order_id)
        .order_by(OrderStatusLog.created_at.desc())
        .all()
    )

    return logs
