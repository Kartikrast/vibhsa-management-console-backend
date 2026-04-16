"""
Webhook event handler dispatch system.
Maps (event_type, resource_name) → handler function.
Each handler receives (db, event) and performs domain-specific logic.
"""
import logging

from sqlalchemy.orm import Session

from app.models.walmart_webhook import WalmartWebhookEvent
from app.services.webhook_handlers.order_handler import handle_order_event
from app.services.webhook_handlers.item_handler import handle_item_event
from app.services.webhook_handlers.price_handler import handle_price_event
from app.services.webhook_handlers.inventory_handler import handle_inventory_event

logger = logging.getLogger(__name__)

# Registry: resource_name → handler function
RESOURCE_HANDLERS = {
    "ORDER": handle_order_event,
    "ITEM": handle_item_event,
    "PRICE": handle_price_event,
    "INVENTORY": handle_inventory_event,
}


def dispatch_event(db: Session, event: WalmartWebhookEvent):
    """Dispatch an incoming webhook event to the appropriate handler."""
    handler = RESOURCE_HANDLERS.get(event.resource_name)
    if handler:
        handler(db=db, event=event)
    else:
        logger.info(
            "No handler for resource_name=%s event_type=%s, storing only",
            event.resource_name, event.event_type,
        )
