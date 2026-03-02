"""Base data connector — interface for all integrations.

Connects to:
- ERP (NetSuite, SAP, Oracle)
- Billing systems
- Payment providers
- E-commerce platforms
- Data warehouses (Snowflake, BigQuery)
- Tax engines
- External regulation feeds
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from taxinfra.models.transaction import Transaction


class SyncStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SyncResult(BaseModel):
    """Result of a data sync operation."""

    sync_id: str = Field(default_factory=lambda: str(uuid4()))
    connector_name: str
    status: SyncStatus
    started_at: datetime
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    records_fetched: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    errors: list[str] = Field(default_factory=list)


class DataConnector(ABC):
    """Base class for all data source integrations.

    Each connector handles:
    1. Authentication with the source system
    2. Extracting transaction data
    3. Mapping to the canonical Transaction model
    4. Incremental sync (only fetch new/changed records)
    """

    connector_name: str = ""
    source_system: str = ""

    @abstractmethod
    async def connect(self, credentials: dict) -> bool:
        """Establish connection to the source system."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the source system."""
        ...

    @abstractmethod
    async def fetch_transactions(
        self,
        *,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> list[Transaction]:
        """Fetch transactions from the source system.

        Args:
            since: Only fetch transactions created/modified after this time.
            limit: Maximum number of records to fetch.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the connection to the source system is healthy."""
        ...

    async def sync(self, since: datetime | None = None) -> SyncResult:
        """Run a full sync cycle: fetch, map, and return results."""
        started_at = datetime.utcnow()
        errors: list[str] = []

        try:
            transactions = await self.fetch_transactions(since=since)
            return SyncResult(
                connector_name=self.connector_name,
                status=SyncStatus.SUCCESS,
                started_at=started_at,
                records_fetched=len(transactions),
                records_created=len(transactions),
            )
        except Exception as e:
            errors.append(str(e))
            return SyncResult(
                connector_name=self.connector_name,
                status=SyncStatus.FAILED,
                started_at=started_at,
                errors=errors,
            )
