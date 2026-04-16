"""
Webhook endpoints for marketplace events.
Handles incoming notifications from Walmart (orders, items, prices, inventory, reports).
"""
import base64
import hmac
import logging

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.database import get_db
from app.models.walmart_webhook import WalmartWebhookEvent
from app.services.marketplace_reports.walmart_report_service import handle_walmart_report_webhook
from app.services.webhook_handlers import dispatch_event

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _validate_basic_auth(request: Request) -> bool:
    """Validate BASIC_AUTH header from Walmart using constant-time comparison."""
    auth_header = request.headers.get(settings.WALMART_WEBHOOK_AUTH_HEADER)
    if not auth_header:
        return False

    # Handle "Basic <base64>" format
    if auth_header.startswith("Basic "):
        encoded = auth_header[6:]
    else:
        encoded = auth_header

    try:
        expected = base64.b64encode(
            f"{settings.WALMART_WEBHOOK_USERNAME}:{settings.WALMART_WEBHOOK_PASSWORD}".encode()
        ).decode()
        return hmac.compare_digest(encoded, expected)
    except Exception:
        return False


@router.post("/walmart/events")
async def walmart_event_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Generic webhook receiver for all Walmart event notifications.
    Validates BASIC_AUTH, stores event for idempotency, dispatches to handler.
    """
    # Validate auth
    if not _validate_basic_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Extract event metadata from payload
    event_id = payload.get("eventId") or payload.get("event_id")
    event_type = payload.get("eventType") or payload.get("event_type")
    event_version = payload.get("eventVersion") or payload.get("event_version", "V1")
    resource_name = payload.get("resourceName") or payload.get("resource_name", "")

    if not event_id or not event_type:
        logger.warning("Missing eventId or eventType in webhook payload", extra={"payload": payload})
        raise HTTPException(status_code=400, detail="Missing eventId or eventType")

    # Idempotency check + store
    event = WalmartWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        event_version=event_version,
        resource_name=resource_name,
        payload=payload,
        status="RECEIVED",
    )
    try:
        db.add(event)
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info("Duplicate webhook event, skipping", extra={"event_id": event_id})
        return {"status": "duplicate", "event_id": event_id}

    # Dispatch to handler
    try:
        dispatch_event(db=db, event=event)
        event.status = "PROCESSED"
    except Exception as e:
        logger.exception("Webhook event handler failed", extra={"event_id": event_id, "event_type": event_type})
        event.status = "FAILED"
        event.error = str(e)[:1000]

    from datetime import datetime, timezone
    event.processed_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": event.status, "event_id": event_id}


@router.post("/walmart/orders")
async def walmart_order_webhook(request: Request):
    """
    Placeholder for Walmart order event webhooks.
    Walmart can push: order.created, order.statusChange, etc.

    TODO (when Walmart webhook integration is ready):
    - Validate HMAC signature from Walmart headers
    - Parse event type and dispatch to import/update service
    - Log OrderStatusLog entries with source = "WEBHOOK"
    """
    payload = await request.json()
    logger.info("Walmart order webhook received", extra={"payload": payload})
    return {"status": "received"}


@router.post("/walmart/reports")
async def walmart_report_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle Walmart report completion/failure webhooks.
    Walmart pushes: report.completed, report.failed

    Headers expected:
    - X-Event-Type: "report.completed" or "report.failed"
    - X-Event-Id: Unique event identifier for idempotency
    - X-Request-Id: The report request ID

    TODO: Add HMAC signature validation when Walmart provides webhook secrets
    """
    try:
        payload = await request.json()
        headers = request.headers

        event_type = headers.get("x-event-type")
        event_id = headers.get("x-event-id")
        request_id = headers.get("x-request-id") or payload.get("requestId")

        if not event_type or not event_id or not request_id:
            logger.warning("Missing required headers for Walmart report webhook", extra={
                "headers": dict(headers),
                "payload": payload
            })
            raise HTTPException(status_code=400, detail="Missing required headers")

        logger.info("Walmart report webhook received", extra={
            "event_type": event_type,
            "event_id": event_id,
            "request_id": request_id,
            "payload": payload
        })

        # Process the webhook
        report_request = handle_walmart_report_webhook(
            db=db,
            event_type=event_type,
            event_id=event_id,
            request_id=request_id,
            payload=payload,
        )

        logger.info("Walmart report webhook processed successfully", extra={
            "report_id": str(report_request.id),
            "status": report_request.status
        })

        return {"status": "processed"}

    except ValueError as e:
        logger.error("Walmart report webhook processing failed", extra={
            "error": str(e),
            "headers": dict(request.headers) if request else None
        })
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in Walmart report webhook", extra={
            "error": str(e),
            "headers": dict(request.headers) if request else None
        })
        raise HTTPException(status_code=500, detail="Internal server error")
