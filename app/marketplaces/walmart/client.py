import httpx
import uuid
import base64
from datetime import datetime, timedelta

from app.core.config import get_settings

settings = get_settings()

class WalmartClient:
    def __init__(self, account):
        """
        account = MarketplaceAccount DB object
        """
        self.account = account
        if settings.WALMART_ENV == "production":
            self.base_url = settings.WALMART_PRODUCTION_URL
        else:
            self.base_url = settings.WALMART_SANDBOX_URL

    def _get_headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "WM_SVC.NAME": "Vibhsa",
            "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
            "WM_CONSUMER.CHANNEL.TYPE": "10001029243",  # from Walmart portal
            "WM_SEC.ACCESS_TOKEN": self.account.access_token,
        }

    def _refresh_token_if_needed(self, db):
        if not self.account.token_expiry:
            return

        if datetime.utcnow() < self.account.token_expiry:
            return  # still valid

        # refresh token
        response = httpx.post(
            f"{self.base_url}/v3/token",
            data={"grant_type": "client_credentials"},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "WM_SVC.NAME": "Vibhsa",
                "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
            },
            auth=(self.account.client_id, self.account.client_secret),
        )

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        token_data = response.json()

        self.account.access_token = token_data["access_token"]
        self.account.token_expiry = datetime.utcnow() + timedelta(
            seconds=token_data["expires_in"]
        )

        db.commit()

    def request(self, method, endpoint, db, **kwargs):
        """
        Centralized request method
        """
        self._refresh_token_if_needed(db)

        url = f"{self.base_url}{endpoint}"

        response = httpx.request(
            method,
            url,
            headers=self._get_headers(),
            **kwargs,
        )

        if response.status_code >= 400:
            raise Exception(f"Walmart API error: {response.text}")

        return response.json()

    def get_items(self, db, limit: int = 10):
        """
        Fetch product listings from Walmart.
        """
        endpoint = f"/v3/items?limit={limit}"

        return self.request(
            method="GET",
            endpoint=endpoint,
            db=db,
        )
