import httpx
import logging
import csv
import gzip
import io
import time
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class AmazonClient:
    """
    Amazon SP-API client.

    Auth uses Login with Amazon (LWA) OAuth 2.0:
      - grant_type = refresh_token
      - Requires client_id, client_secret, and a long-lived refresh_token
      - Returns a short-lived access_token (~1 hour)
    """

    LWA_TOKEN_URL = settings.AMAZON_LWA_ENDPOINT

    def __init__(self, account=None, client_id=None, client_secret=None, refresh_token=None, region=None):
        """
        account → MarketplaceAccount (normal usage)
        OR
        client_id + client_secret + refresh_token → bootstrap mode (connect flow)
        """
        self.account = account

        if account:
            self.client_id = account.client_id
            self.client_secret = account.client_secret
            self.refresh_token = account.refresh_token
            self.region = account.region
        else:
            self.client_id = client_id
            self.client_secret = client_secret
            self.refresh_token = refresh_token
            self.region = region or "US"

        if settings.AMAZON_ENV == "production":
            self.base_url = settings.AMAZON_PRODUCTION_US_URL
        else:
            self.base_url = settings.AMAZON_SANDBOX_US_URL

    # ========================
    # AUTH — LWA TOKEN
    # ========================

    def get_access_token(self) -> dict:
        """
        Exchange the long-lived refresh_token for a short-lived access_token.
        Used during the connect flow to validate credentials.

        Returns: {"access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 3600}
        """
        response = httpx.post(
            self.LWA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            },
        )

        if response.status_code != 200:
            logger.error("Amazon LWA token request failed: %s", response.text)
            raise Exception(f"Amazon token generation failed: {response.text}")

        return response.json()

    def _refresh_token_if_needed(self, db):
        """
        Check if the stored access_token has expired and refresh it via LWA.
        Persists the new token + expiry back to the MarketplaceAccount row.
        """
        if not self.account:
            return

        if not self.account.token_expiry:
            return

        if datetime.now(timezone.utc) < self.account.token_expiry:
            return  # still valid

        logger.info("Amazon access token expired, refreshing…")

        response = httpx.post(
            self.LWA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.account.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            },
        )

        if response.status_code != 200:
            logger.error("Amazon LWA token refresh failed: %s", response.text)
            raise Exception(f"Amazon token refresh failed: {response.text}")

        token_data = response.json()

        self.account.access_token = token_data["access_token"]
        self.account.token_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=token_data["expires_in"]
        )

        # LWA may rotate the refresh_token — persist if returned
        if token_data.get("refresh_token"):
            self.account.refresh_token = token_data["refresh_token"]

        db.commit()
        logger.info("Amazon access token refreshed successfully")

    # ========================
    # GENERIC REQUEST
    # ========================

    def _get_headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-amz-access-token": self.account.access_token,
        }

    def request(self, method, endpoint, db, **kwargs):
        """
        Centralized request method — auto-refreshes token before each call.
        """
        self._refresh_token_if_needed(db)

        url = f"{self.base_url}{endpoint}"

        logger.info("Amazon request: %s %s | payload=%s", method, url, kwargs.get("json"))

        response = httpx.request(
            method,
            url,
            headers=self._get_headers(),
            **kwargs,
        )

        if response.status_code >= 400:
            logger.error("Amazon SP-API error [%s %s]: %s", method, endpoint, response.text)
            raise Exception(f"Amazon API error: {response.text}")

        return response.json()

    # ========================
    # REGION → MARKETPLACE ID
    # ========================

    REGION_MARKETPLACE_MAP = {
        "US": "ATVPDKIKX0DER",
        "CA": "A2EUQ1WTGCTBG2",
        "MX": "A1AM78C64UM0Y8",
        "UK": "A1F83G8C2ARO7P",
        "DE": "A1PA6795UKMFR9",
        "FR": "A13V1IB3VIYZZH",
        "IT": "APJ6JRA9NG5V4",
        "ES": "A1RKKUPIHCS9HS",
        "IN": "A21TJRUUN4KGV",
        "JP": "A1VC38T7YXB528",
        "AU": "A39IBJ37TRP1C6",
    }

    @property
    def marketplace_id(self) -> str:
        return self.REGION_MARKETPLACE_MAP.get(self.region, "ATVPDKIKX0DER")

    # ========================
    # LISTINGS — REPORTS API
    # ========================

    def create_report(self, db, report_type: str = "GET_MERCHANT_LISTINGS_ALL_DATA") -> str:
        """
        Request a new report.
        POST /reports/2021-06-30/reports

        Returns the reportId.
        """
        payload = {
            "reportType": report_type,
            "marketplaceIds": [self.marketplace_id],
        }
        data = self.request("POST", "/reports/2021-06-30/reports", db, json=payload)
        report_id = data.get("reportId")
        logger.info("Amazon report created: %s (type=%s)", report_id, report_type)
        return report_id

    def get_report(self, db, report_id: str) -> dict:
        """
        Check report status.
        GET /reports/2021-06-30/reports/{reportId}

        Returns full report object with processingStatus.
        """
        return self.request("GET", f"/reports/2021-06-30/reports/{report_id}", db)

    def get_report_document(self, db, report_document_id: str) -> dict:
        """
        Get the download URL for a completed report.
        GET /reports/2021-06-30/documents/{reportDocumentId}

        Returns {"url": "...", "compressionAlgorithm": "GZIP" | None}
        """
        return self.request("GET", f"/reports/2021-06-30/documents/{report_document_id}", db)

    def _download_and_parse_tsv(self, url: str, compression: str | None = None) -> list[dict]:
        """
        Download a report document and parse its TSV content into a list of dicts.
        """
        resp = httpx.get(url, timeout=60)
        resp.raise_for_status()

        raw_bytes = resp.content

        if compression and compression.upper() == "GZIP":
            raw_bytes = gzip.decompress(raw_bytes)

        text = raw_bytes.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        return [row for row in reader]

    def get_listings(
        self,
        db,
        poll_interval: int = 5,
        max_wait: int = 120,
    ) -> list[dict]:
        """
        High-level method: create a report, poll until done, download and parse.

        Returns a list of dicts, one per listing row from the TSV report.
        """
        report_id = self.create_report(db)

        elapsed = 0
        while elapsed < max_wait:
            report = self.get_report(db, report_id)
            status = report.get("processingStatus")

            if status == "DONE":
                report_document_id = report.get("reportDocumentId")
                break
            elif status in ("CANCELLED", "FATAL"):
                raise Exception(f"Amazon report {report_id} failed with status: {status}")

            logger.info("Report %s status: %s — waiting %ds", report_id, status, poll_interval)
            time.sleep(poll_interval)
            elapsed += poll_interval
        else:
            raise Exception(f"Amazon report {report_id} timed out after {max_wait}s")

        doc = self.get_report_document(db, report_document_id)
        download_url = doc.get("url")
        compression = doc.get("compressionAlgorithm")

        listings = self._download_and_parse_tsv(download_url, compression)
        logger.info("Downloaded %d listings from report %s", len(listings), report_id)
        return listings