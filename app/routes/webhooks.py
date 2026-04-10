"""
Webhook endpoints for marketplace order events.
Currently a placeholder — logs incoming payloads for future implementation.
"""
import logging

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.marketplace_reports.walmart_report_service import handle_walmart_report_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


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
