"""
Inventory helpers for order management.
Uses SELECT ... FOR UPDATE to prevent race conditions on concurrent order processing.
"""
import logging
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.marketplace_account import MarketplaceAccount
from app.marketplaces.adapter_registry import get_inventory_adapter
from app.models.inventory import Inventory

logger = logging.getLogger(__name__)

def update_marketplace_inventory(
    db: Session,
    account: MarketplaceAccount,
    sku: str,
    new_quantity: int,
) -> bool:
    """
    Update inventory on the marketplace for a specific SKU.
    Returns True if update succeeded, False otherwise.
    """
    adapter = get_inventory_adapter(account.marketplace, account)
    return adapter.update_inventory(db, sku, new_quantity)


def _get_inventory_row(
    db: Session,
    org_id: uuid.UUID,
    variant_id: uuid.UUID,
    lock: bool = True,
) -> Inventory | None:
    """
    Get the default-location inventory row for a variant.
    Optionally acquires a row-level lock (FOR UPDATE).
    """
    query = db.query(Inventory).filter(
        and_(
            Inventory.organization_id == org_id,
            Inventory.product_variant_id == variant_id,
            Inventory.location_name == "default",
        )
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def reserve_inventory(
    db: Session,
    org_id: uuid.UUID,
    variant_id: uuid.UUID,
    qty: int,
) -> bool:
    """
    Reserve inventory when an order is acknowledged.
    Increments quantity_reserved by qty.
    Returns True if reservation succeeded, False if no inventory row found.
    """
    row = _get_inventory_row(db, org_id, variant_id, lock=True)
    if not row:
        logger.warning(
            "No inventory row for variant %s in org %s — skipping reservation",
            variant_id, org_id,
        )
        return False

    row.quantity_reserved += qty
    db.flush()
    return True


def deduct_inventory(
    db: Session,
    org_id: uuid.UUID,
    variant_id: uuid.UUID,
    qty: int,
) -> bool:
    """
    Deduct inventory when an order line is shipped.
    Decrements quantity_available and quantity_reserved by qty.
    Returns True if deduction succeeded.
    """
    row = _get_inventory_row(db, org_id, variant_id, lock=True)
    if not row:
        logger.warning(
            "No inventory row for variant %s in org %s — skipping deduction",
            variant_id, org_id,
        )
        return False

    row.quantity_available = max(0, row.quantity_available - qty)
    row.quantity_reserved = max(0, row.quantity_reserved - qty)
    db.flush()
    return True


def release_reservation(
    db: Session,
    org_id: uuid.UUID,
    variant_id: uuid.UUID,
    qty: int,
) -> bool:
    """
    Release reserved inventory when an order line is cancelled.
    Decrements quantity_reserved by qty.
    Returns True if release succeeded.
    """
    row = _get_inventory_row(db, org_id, variant_id, lock=True)
    if not row:
        logger.warning(
            "No inventory row for variant %s in org %s — skipping release",
            variant_id, org_id,
        )
        return False

    row.quantity_reserved = max(0, row.quantity_reserved - qty)
    db.flush()
    return True
