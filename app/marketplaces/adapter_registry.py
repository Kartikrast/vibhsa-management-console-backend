from app.marketplaces.base_adapter import MarketplaceOrderAdapter
from app.models.marketplace_account import MarketplaceAccount


def get_order_adapter(marketplace: str, account: MarketplaceAccount) -> MarketplaceOrderAdapter:
    """
    Resolve the correct order adapter for a given marketplace.
    New marketplaces only need to implement MarketplaceOrderAdapter and register here.
    """
    if marketplace == "walmart":
        from app.marketplaces.walmart.order_adapter import WalmartOrderAdapter
        return WalmartOrderAdapter(account)

    raise ValueError(f"Unsupported marketplace: {marketplace}")
