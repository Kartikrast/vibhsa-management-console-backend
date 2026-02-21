"""
Periodic order sync task.
Fetches new/updated orders from all active marketplace accounts.
"""
import logging

from app.core.database import SessionLocal
from app.models.marketplace_account import MarketplaceAccount
from app.services.order_import.order_import_service import import_orders

logger = logging.getLogger(__name__)


def sync_all_orders():
    """
    Background job that runs on a configurable interval.
    Iterates all active marketplace accounts and imports orders.
    """
    db = SessionLocal()
    try:
        accounts = (
            db.query(MarketplaceAccount)
            .filter(MarketplaceAccount.is_active.is_(True))
            .all()
        )

        for account in accounts:
            try:
                result = import_orders(
                    db=db,
                    organization_id=account.organization_id,
                    marketplace_account=account,
                )
                logger.info(
                    "Order sync for %s/%s: imported=%d updated=%d skipped=%d",
                    account.marketplace,
                    account.id,
                    result["imported"],
                    result["updated"],
                    result["skipped"],
                )
            except Exception:
                logger.exception(
                    "Order sync failed for account %s (%s)",
                    account.id,
                    account.marketplace,
                )
    finally:
        db.close()
