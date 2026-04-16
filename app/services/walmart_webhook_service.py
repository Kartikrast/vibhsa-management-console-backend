import logging
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.walmart_webhook import WalmartWebhookSubscription
from app.models.marketplace_account import MarketplaceAccount
from app.marketplaces.walmart.client import WalmartClient
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_event_types(db: Session, account: MarketplaceAccount):
    client = WalmartClient(account)
    return client.get_event_types(db=db)


def _build_auth_details() -> dict:
    """Build BASIC_AUTH details from settings."""
    return {
        "authMethod": "BASIC_AUTH",
        "userName": settings.WALMART_WEBHOOK_USERNAME,
        "password": settings.WALMART_WEBHOOK_PASSWORD,
        "authHeaderName": settings.WALMART_WEBHOOK_AUTH_HEADER,
    }


def _build_event_url() -> str:
    """Build the webhook receiver URL from settings."""
    base = settings.WALMART_WEBHOOK_BASE_URL.rstrip("/")
    return f"{base}/webhooks/walmart/events"


def create_subscriptions(
    db: Session,
    account: MarketplaceAccount,
    organization_id: UUID,
    events: list,
):
    """
    Create webhook subscriptions with Walmart and store in DB.
    Each event dict should have: eventType, eventVersion, resourceName.
    eventUrl and authDetails are filled from settings if not provided.
    """
    event_url = _build_event_url()
    auth_details = _build_auth_details()

    # Fill defaults for each event
    walmart_events = []
    for ev in events:
        event_payload = {
            "eventType": ev.get("eventType") or ev.get("event_type"),
            "eventVersion": ev.get("eventVersion") or ev.get("event_version", "V1"),
            "resourceName": ev.get("resourceName") or ev.get("resource_name"),
            "eventUrl": ev.get("eventUrl") or ev.get("event_url") or event_url,
            "authDetails": ev.get("authDetails") or ev.get("auth_details") or auth_details,
        }
        walmart_events.append(event_payload)

    client = WalmartClient(account)
    response = client.create_subscriptions(db=db, events=walmart_events)

    # Store subscriptions in DB
    created = response.get("events") or response.get("subscriptions") or []
    if isinstance(response, list):
        created = response

    for sub in created:
        sub_id = sub.get("subscriptionId")
        if not sub_id:
            continue
        db_sub = WalmartWebhookSubscription(
            organization_id=organization_id,
            marketplace_account_id=account.id,
            external_subscription_id=sub_id,
            event_type=sub.get("eventType", ""),
            event_version=sub.get("eventVersion", "V1"),
            resource_name=sub.get("resourceName", ""),
            event_url=sub.get("eventUrl", event_url),
            status=sub.get("status", "ACTIVE"),
        )
        db.add(db_sub)

    db.commit()
    return response


def list_subscriptions(
    db: Session,
    account: MarketplaceAccount,
    subscription_id: str = None,
    event_type: str = None,
    resource_name: str = None,
    status: str = None,
):
    client = WalmartClient(account)
    return client.get_all_subscriptions(
        db=db,
        subscription_id=subscription_id,
        event_type=event_type,
        resource_name=resource_name,
        status=status,
    )


def update_subscription(
    db: Session,
    account: MarketplaceAccount,
    subscription_id: str,
    updates: dict,
):
    client = WalmartClient(account)
    response = client.update_subscription(db=db, subscription_id=subscription_id, **updates)

    # Update local record if exists
    db_sub = db.query(WalmartWebhookSubscription).filter(
        WalmartWebhookSubscription.external_subscription_id == subscription_id,
        WalmartWebhookSubscription.marketplace_account_id == account.id,
    ).first()
    if db_sub:
        if "eventType" in updates:
            db_sub.event_type = updates["eventType"]
        if "eventVersion" in updates:
            db_sub.event_version = updates["eventVersion"]
        if "resourceName" in updates:
            db_sub.resource_name = updates["resourceName"]
        if "eventUrl" in updates:
            db_sub.event_url = updates["eventUrl"]
        if "status" in updates:
            db_sub.status = updates["status"]
        db.commit()

    return response


def delete_subscription(
    db: Session,
    account: MarketplaceAccount,
    subscription_id: str,
):
    client = WalmartClient(account)
    response = client.delete_subscription(db=db, subscription_id=subscription_id)

    # Remove local record
    db_sub = db.query(WalmartWebhookSubscription).filter(
        WalmartWebhookSubscription.external_subscription_id == subscription_id,
        WalmartWebhookSubscription.marketplace_account_id == account.id,
    ).first()
    if db_sub:
        db.delete(db_sub)
        db.commit()

    return response


def send_test_notification(
    db: Session,
    account: MarketplaceAccount,
    event_type: str,
    event_version: str,
    resource_name: str,
    event_url: str = None,
):
    url = event_url or _build_event_url()
    auth_details = _build_auth_details()

    client = WalmartClient(account)
    return client.test_notification(
        db=db,
        event_type=event_type,
        event_version=event_version,
        resource_name=resource_name,
        event_url=url,
        auth_details=auth_details,
    )
