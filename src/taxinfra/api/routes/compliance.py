"""Compliance API endpoints — tax determination, filing, reconciliation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from taxinfra.compliance.anomaly import AnomalyDetector
from taxinfra.models.transaction import Transaction, TransactionLineItem, TransactionType

router = APIRouter()


class TaxDeterminationRequest(BaseModel):
    """Request to determine tax on a transaction."""

    transaction_type: str = "sale"
    transaction_date: str  # ISO date
    currency: str = "USD"
    seller_country: str
    buyer_country: str
    buyer_jurisdiction: str = ""
    is_b2b: bool = False
    is_cross_border: bool = False
    is_digital_service: bool = False
    net_amount: str  # Decimal as string
    description: str = ""


class TaxDeterminationResponse(BaseModel):
    """Response with tax determination results."""

    jurisdiction_code: str
    tax_type: str
    taxable_amount: str
    tax_rate: str
    tax_amount: str
    is_exempt: bool = False
    is_reverse_charge: bool = False
    rules_applied: list[str] = Field(default_factory=list)


@router.post("/determine-tax")
async def determine_tax(
    body: TaxDeterminationRequest,
    request: Request,
) -> dict:
    """Determine tax on a transaction using country-specific rules."""
    registry = request.app.state.country_registry

    # Build a Transaction from the request
    net_amount = Decimal(body.net_amount)

    # Normalize jurisdiction code: "CA" -> "US-CA" if country is provided
    buyer_jurisdiction = body.buyer_jurisdiction
    if buyer_jurisdiction and "-" not in buyer_jurisdiction and body.buyer_country:
        buyer_jurisdiction = f"{body.buyer_country}-{buyer_jurisdiction}"

    transaction = Transaction(
        transaction_type=TransactionType(body.transaction_type),
        transaction_date=datetime.fromisoformat(body.transaction_date),
        currency=body.currency,
        seller_country=body.seller_country,
        buyer_country=body.buyer_country,
        buyer_jurisdiction=buyer_jurisdiction,
        is_b2b=body.is_b2b,
        is_cross_border=body.is_cross_border,
        is_digital_service=body.is_digital_service,
        line_items=[
            TransactionLineItem(
                line_number=1,
                description=body.description or "Tax determination request",
                quantity=Decimal("1"),
                unit_price=net_amount,
                net_amount=net_amount,
            )
        ],
    )

    # Determine which country module to use (buyer's country for destination-based)
    country_code = body.buyer_country or body.seller_country
    module = registry.get(country_code)
    if not module:
        return {
            "error": f"No country module for {country_code}",
            "available_countries": registry.list_countries(),
        }

    determinations = module.determine_tax(transaction)

    return {
        "determinations": [
            TaxDeterminationResponse(
                jurisdiction_code=d.jurisdiction_code,
                tax_type=d.tax_type,
                taxable_amount=str(d.taxable_amount),
                tax_rate=str(d.tax_rate),
                tax_amount=str(d.tax_amount),
                is_exempt=d.is_exempt,
                is_reverse_charge=d.is_reverse_charge,
                rules_applied=d.rules_applied,
            ).model_dump()
            for d in determinations
        ]
    }


@router.get("/countries")
async def list_countries(request: Request) -> dict:
    """List available country modules."""
    registry = request.app.state.country_registry
    countries = []
    for code in registry.list_countries():
        module = registry.get(code)
        if module:
            countries.append({
                "code": module.country_code,
                "name": module.country_name,
                "currency": module.currency,
                "tax_types": [str(t) for t in module.tax_types],
            })
    return {"countries": countries}


@router.get("/countries/{country_code}/jurisdictions")
async def get_jurisdictions(country_code: str, request: Request) -> dict:
    """Get jurisdictions for a country."""
    registry = request.app.state.country_registry
    module = registry.get(country_code)
    if not module:
        return {"error": f"No country module for {country_code}"}

    jurisdictions = module.get_jurisdictions()
    return {
        "country": country_code,
        "jurisdictions": [j.model_dump() for j in jurisdictions],
    }


@router.get("/traceability/{entity_type}/{entity_id}")
async def get_trace_chain(
    entity_type: str,
    entity_id: str,
    request: Request,
) -> dict:
    """Get the full traceability chain for an entity."""
    chain = request.app.state.trace_chain.get_full_chain(entity_type, entity_id)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "chain": [link.model_dump() for link in chain],
    }
