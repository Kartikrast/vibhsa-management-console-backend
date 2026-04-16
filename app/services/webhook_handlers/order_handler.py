"""Handler for ORDER resource events (e.g., order.created, order.statusChange, order.autocancelled)."""
import logging
from sqlalchemy.orm import Session
from app.models.walmart_webhook import WalmartWebhookEvent

logger = logging.getLogger(__name__)


def handle_order_event(db: Session, event: WalmartWebhookEvent):
    logger.info(
        "ORDER event received: type=%s id=%s",
        event.event_type, event.event_id,
        extra={"payload": event.payload},
    )
    # TODO: Implement order status updates, new order imports, etc.
