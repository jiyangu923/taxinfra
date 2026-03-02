"""FastAPI application — the tax operations API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from taxinfra.api.routes import agents, compliance, health
from taxinfra.core.audit_trail import AuditTrail
from taxinfra.core.explainability import DecisionLog
from taxinfra.core.traceability import TraceChain
from taxinfra.countries.registry import CountryRegistry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared services on startup."""
    app.state.audit_trail = AuditTrail()
    app.state.decision_log = DecisionLog()
    app.state.trace_chain = TraceChain()
    app.state.country_registry = CountryRegistry.create_default()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="taxinfra",
        description="AI-native indirect tax operations infrastructure",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
    app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["compliance"])

    return app


app = create_app()
