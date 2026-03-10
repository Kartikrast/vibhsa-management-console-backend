from sqlalchemy.orm import Session

from app.marketplaces.base_adapter import MarketplaceInventoryAdapter
from app.marketplaces.walmart.client import WalmartClient
from app.models.marketplace_account import MarketplaceAccount

class WalmartInventoryAdapter(MarketplaceInventoryAdapter):
    def __init__(self, account: MarketplaceAccount):
        self.account = account
        self.client = WalmartClient(account)

    def update_inventory(self, db: Session, sku: str, new_quantity: int) -> bool:
        """
        Update inventory quantity for a specific product variant on Walmart.
        Returns True if update succeeded, False otherwise.
        """
        try:
            self.client.update_inventory(db, sku=sku, quantity=new_quantity)
            return True
        except Exception as e:
            # Log the error in a real implementation
            print(f"Error updating inventory on Walmart for SKU {sku}: {e}")
            return False