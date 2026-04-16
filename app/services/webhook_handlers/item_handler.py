"""Handler for ITEM resource events (e.g., OFFER_UNPUBLISHED, OFFER_PUBLISHED)."""
import logging
from sqlalchemy.orm import Session
from app.models.walmart_webhook import WalmartWebhookEvent

logger = logging.getLogger(__name__)


def handle_item_event(db: Session, event: WalmartWebhookEvent):
    logger.info(
        "ITEM event received: type=%s id=%s",
        event.event_type, event.event_id,
        extra={"payload": event.payload},
    )
    # TODO: Implement item publish/unpublish status sync, content change tracking, etc.
