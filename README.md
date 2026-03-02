# taxinfra

AI-native indirect tax operations infrastructure. A programmable tax operating system that replaces traditional consulting + fragmented tax software with a fleet of specialized AI agents.

## Architecture

```
src/taxinfra/
├── agents/          # Specialized AI tax agents
│   ├── base.py      # Base agent with audit trail, memory, explainability
│   ├── planning.py  # Tax planning (new markets, M&A, regulation changes)
│   ├── compliance.py    # End-to-end filing workflow
│   ├── audit_defense.py # Tax authority audit response
│   └── regulatory.py    # Regulation change monitoring
├── core/            # Trust layer infrastructure
│   ├── audit_trail.py    # Immutable log of every system action
│   ├── explainability.py # Decision reasoning chains with rule references
│   └── traceability.py   # Filing → transaction → API → ledger links
├── models/          # Canonical data models
│   ├── transaction.py    # Tax-relevant transactions
│   ├── entity.py         # Corporate entity structure
│   ├── filing.py         # Tax return filings
│   └── jurisdiction.py   # Jurisdictions, rates, rules
├── countries/       # Country skill library (Tax Intelligence Graph)
│   ├── base.py      # Country module interface
│   ├── us.py        # US sales & use tax
│   ├── uk.py        # UK VAT (MTD-compatible)
│   ├── de.py        # German Umsatzsteuer
│   └── registry.py  # Country module registry
├── compliance/      # Compliance engine
│   ├── filing.py         # Return generation from transactions
│   ├── reconciliation.py # GL reconciliation
│   └── anomaly.py        # Anomaly detection
├── integrations/    # Data integration layer
│   └── erp/         # ERP connectors (NetSuite, SAP)
└── api/             # FastAPI REST API
    └── routes/      # Agent invocation, tax determination, compliance
```

## Quick Start

```bash
pip install -e ".[dev]"
pytest
uvicorn taxinfra.api.app:app --reload
```

## Key Differentiators

- **Traceability**: Every filing traces back to source transactions, API calls, and ledger entries
- **Explainability**: Every AI decision shows its reasoning, rules applied, and data used
- **Audit trail**: Immutable log of every action — agent, human, and system
- **Country modules**: Jurisdiction-specific rules, filing schemas, penalty logic, e-invoicing standards
- **Human-in-the-loop**: All filings require human approval before submission
