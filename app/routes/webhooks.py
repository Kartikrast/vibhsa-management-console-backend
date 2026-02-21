"""
Webhook endpoints for marketplace order events.
Currently a placeholder — logs incoming payloads for future implementation.
"""
import logging

from fastapi import APIRouter, Request

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
