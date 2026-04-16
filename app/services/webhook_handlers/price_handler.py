"""Handler for PRICE resource events (e.g., buybox changes, price updates)."""
import logging
from sqlalchemy.orm import Session
from app.models.walmart_webhook import WalmartWebhookEvent

logger = logging.getLogger(__name__)


def handle_price_event(db: Session, event: WalmartWebhookEvent):
    logger.info(
        "PRICE event received: type=%s id=%s",
        event.event_type, event.event_id,
        extra={"payload": event.payload},
    )
    # TODO: Implement buybox tracking, price change alerts, etc.
