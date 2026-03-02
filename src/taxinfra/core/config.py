"""Application configuration."""

from __future__ import annotations

from pydantic import BaseModel


class Settings(BaseModel):
    """Global application settings."""

    app_name: str = "taxinfra"
    debug: bool = False
    database_url: str = "sqlite:///taxinfra.db"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Agent settings
    agent_max_iterations: int = 10
    agent_temperature: float = 0.0

    # Filing settings
    auto_submit_filings: bool = False
    require_human_approval: bool = True

    # Audit trail
    audit_trail_enabled: bool = True
