"""NetSuite ERP connector."""

from __future__ import annotations

from datetime import datetime

import httpx

from taxinfra.integrations.base import DataConnector
from taxinfra.models.transaction import Transaction


class NetSuiteConnector(DataConnector):
    connector_name = "netsuite"
    source_system = "netsuite"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._base_url: str = ""
        self._account_id: str = ""

    async def connect(self, credentials: dict) -> bool:
        """Connect to NetSuite via SuiteTalk REST API.

        Expected credentials:
        - account_id: NetSuite account ID
        - consumer_key: OAuth consumer key
        - consumer_secret: OAuth consumer secret
        - token_id: Token-based auth token ID
        - token_secret: Token-based auth token secret
        """
        self._account_id = credentials.get("account_id", "")
        self._base_url = (
            f"https://{self._account_id}.suitetalk.api.netsuite.com/services/rest"
        )
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )
        return True

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_transactions(
        self,
        *,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> list[Transaction]:
        """Fetch transactions from NetSuite.

        In production, this would:
        1. Query SuiteTalk REST API for invoices, credit memos, etc.
        2. Map NetSuite fields to canonical Transaction model
        3. Handle pagination
        4. Support incremental sync via lastModifiedDate
        """
        # Placeholder — real implementation would call NetSuite API
        return []

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            response = await self._client.get("/record/v1/metadata-catalog/")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
