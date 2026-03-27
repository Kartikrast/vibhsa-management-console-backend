from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_context
from app.models.order import Order, OrderLine, OrderStatusLog, OrderStatus
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
    CreateShippingLabelRequest,
)
from app.services.order_service import (
    acknowledge_order,
    ship_order_lines,
    cancel_order_lines,
    refund_order_lines,
    link_order_line_to_variant,
)
from app.services.order_import.order_import_service import import_orders
from app.marketplaces.adapter_registry import get_order_adapter

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


# ========================
# SHIPPING LABELS
# ========================

@router.post("/{order_id}/shipping-label")
def create_shipping_label_route(
    order_id: UUID,
    payload: CreateShippingLabelRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Create a shipping label for an order via Ship With Walmart."""
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

    account = (
        db.query(MarketplaceAccount)
        .filter(MarketplaceAccount.id == order.marketplace_account_id)
        .first()
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marketplace account not found",
        )

    adapter = get_order_adapter(order.marketplace, account)

    if not hasattr(adapter, "create_shipping_label"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shipping labels not supported for {order.marketplace}",
        )

    # If a label already exists locally, return stored label info
    if order.label_tracking_number:
        return {
            "label_exists": True,
            "tracking": order.label_tracking_number,
            "carrier": order.label_carrier,
            "service": order.label_carrier_service_type,
            "tracking_url": order.label_tracking_url,
        }

    # Auto-acknowledge Created orders before generating labels
    if order.status == OrderStatus.CREATED:
        acknowledge_order(
            db=db,
            org_id=organization.id,
            order_id=order.id,
        )
        db.refresh(order)

    # Resolve from_address: payload → account default → error
    label_data = payload.model_dump()

    if not label_data.get("from_address"):
        if account.default_from_address:
            label_data["from_address"] = account.default_from_address
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No from_address provided and no default address configured on marketplace account",
            )

    # Resolve return_address: payload → account default → from_address
    if not label_data.get("return_address"):
        if account.default_return_address:
            label_data["return_address"] = account.default_return_address
        else:
            label_data["return_address"] = label_data["from_address"]

    try:
        result = adapter.create_shipping_label(
            db=db,
            external_order_id=order.external_order_id,
            label_data=label_data,
        )
    except Exception as e:
        # Walmart returns 409 if a label already exists for this order
        if "already generated a label" in str(e):
            label_info = adapter.get_shipping_label(
                db=db,
                external_order_id=order.external_order_id,
            )
            # Parse and persist from the Walmart get-label response
            labels = label_info.get("data", [])
            if labels:
                first_label = labels[0] if isinstance(labels, list) else labels
                order.label_tracking_number = first_label.get("trackingNo")
                order.label_carrier = first_label.get("carrierShortName") or first_label.get("carrierFullName")
                order.label_carrier_service_type = first_label.get("carrierServiceType")
                order.label_tracking_url = first_label.get("trackingUrl")
                db.commit()
            return {
                "label_exists": True,
                "tracking": order.label_tracking_number,
                "carrier": order.label_carrier,
                "service": order.label_carrier_service_type,
                "tracking_url": order.label_tracking_url,
            }
        raise

    # Persist label state on the order
    order.label_tracking_number = result.get("tracking")
    order.label_carrier = result.get("carrier")
    order.label_carrier_service_type = result.get("service")
    order.label_tracking_url = result.get("tracking_url")
    db.commit()

    return {
        "label_exists": False,
        "tracking": order.label_tracking_number,
        "carrier": order.label_carrier,
        "service": order.label_carrier_service_type,
        "tracking_url": order.label_tracking_url,
    }


@router.get("/{order_id}/shipping-label")
def get_shipping_label_route(
    order_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get shipping label details for an order."""
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

    if not order.label_tracking_number:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No shipping label found for this order",
        )

    return {
        "tracking": order.label_tracking_number,
        "carrier": order.label_carrier,
        "service": order.label_carrier_service_type,
        "tracking_url": order.label_tracking_url,
    }


@router.get("/{order_id}/shipping-label/download")
def download_shipping_label_route(
    order_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Download the shipping label PDF for an order."""
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

    if not order.label_tracking_number or not order.label_carrier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No shipping label found for this order. Create a label first.",
        )

    account = (
        db.query(MarketplaceAccount)
        .filter(MarketplaceAccount.id == order.marketplace_account_id)
        .first()
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marketplace account not found",
        )

    adapter = get_order_adapter(order.marketplace, account)

    if not hasattr(adapter, "download_shipping_label"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shipping label download not supported for {order.marketplace}",
        )

    pdf_bytes = adapter.download_shipping_label(
        db=db,
        carrier=order.label_carrier,
        tracking_number=order.label_tracking_number,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="label_{order.external_order_id}_{order.label_tracking_number}.pdf"'
        },
    )


@router.post("/{order_id}/shipping-label/void")
def void_shipping_label_route(
    order_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Void/cancel a shipping label."""
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

    if not order.label_tracking_number or not order.label_carrier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No shipping label found for this order",
        )

    account = (
        db.query(MarketplaceAccount)
        .filter(MarketplaceAccount.id == order.marketplace_account_id)
        .first()
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marketplace account not found",
        )

    adapter = get_order_adapter(order.marketplace, account)

    if not hasattr(adapter, "void_shipping_label"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shipping label void not supported for {order.marketplace}",
        )

    result = adapter.void_shipping_label(
        db=db,
        carrier=order.label_carrier,
        tracking_number=order.label_tracking_number,
    )

    # Clear label state so a new label can be created
    order.label_tracking_number = None
    order.label_carrier = None
    order.label_carrier_service_type = None
    order.label_tracking_url = None
    db.commit()

    return result
