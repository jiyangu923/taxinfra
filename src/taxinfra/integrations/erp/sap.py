"""SAP ERP connector."""

from __future__ import annotations

from datetime import datetime

import httpx

from taxinfra.integrations.base import DataConnector
from taxinfra.models.transaction import Transaction


class SAPConnector(DataConnector):
    connector_name = "sap"
    source_system = "sap"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._base_url: str = ""

    async def connect(self, credentials: dict) -> bool:
        """Connect to SAP via OData API.

        Expected credentials:
        - base_url: SAP system URL
        - username: SAP user
        - password: SAP password
        - client: SAP client number
        """
        self._base_url = credentials.get("base_url", "")
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            auth=(username, password),
            headers={
                "Content-Type": "application/json",
                "sap-client": credentials.get("client", "100"),
            },
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
        """Fetch transactions from SAP.

        In production, this would:
        1. Query SAP OData API for billing documents (VBRK/VBRP)
        2. Map SAP fields to canonical Transaction model
        3. Handle SAP-specific tax codes (MWSKZ) mapping
        4. Support incremental sync via change pointers
        """
        # Placeholder — real implementation would call SAP OData API
        return []

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            response = await self._client.get("/sap/opu/odata/sap/API_BUSINESS_PARTNER/")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
