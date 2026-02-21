from abc import ABC, abstractmethod
from sqlalchemy.orm import Session


class MarketplaceOrderAdapter(ABC):
    """
    Abstract base for marketplace order operations.
    Each marketplace (Walmart, Amazon, Shopify, etc.) implements this interface.
    """

    @abstractmethod
    def fetch_new_orders(self, db: Session, **kwargs) -> list[dict]:
        """Fetch newly released / unacknowledged orders from the marketplace."""
        ...

    @abstractmethod
    def fetch_order(self, db: Session, external_order_id: str) -> dict:
        """Fetch a single order by its marketplace order ID."""
        ...

    @abstractmethod
    def acknowledge_order(self, db: Session, external_order_id: str, lines: list) -> dict:
        """Acknowledge receipt of an order on the marketplace."""
        ...

    @abstractmethod
    def ship_order(self, db: Session, external_order_id: str, lines: list) -> dict:
        """Submit shipping / tracking info for order lines."""
        ...

    @abstractmethod
    def cancel_order(self, db: Session, external_order_id: str, lines: list) -> dict:
        """Cancel one or more order lines on the marketplace."""
        ...

    @abstractmethod
    def refund_order(self, db: Session, external_order_id: str, lines: list) -> dict:
        """Refund one or more order lines on the marketplace."""
        ...
