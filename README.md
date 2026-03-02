# TaxInfra — Agentic AI Tax Infrastructure Platform

An end-to-end **agentic AI infrastructure** for U.S. federal tax workflows.
Users supply a profile and their tax documents; a pipeline of autonomous agents
handles data validation, document processing, tax calculation, and filing —
with minimal additional input required.

---

## Architecture

```
User Input
  │
  ▼
┌────────────────────────────────────────────────────────┐
│               TaxWorkflowOrchestrator                  │
│                                                        │
│  ┌──────────────────┐   ┌─────────────────────────┐   │
│  │ DataCollection   │──▶│  DocumentProcessing     │   │
│  │     Agent        │   │       Agent             │   │
│  └──────────────────┘   └───────────┬─────────────┘   │
│                                     │                  │
│  ┌──────────────────┐   ┌───────────▼─────────────┐   │
│  │   FilingAgent    │◀──│  TaxCalculationAgent    │   │
│  └──────────────────┘   └─────────────────────────┘   │
└────────────────────────────────────────────────────────┘
  │
  ▼
FilingPackage (confirmation, refund/owed, full breakdown)
```

### Agents

| Agent | Responsibility |
|---|---|
| **DataCollectionAgent** | Validates and normalises the user profile; applies defaults |
| **DocumentProcessingAgent** | Extracts income and deduction data from W-2, 1099, 1098, K-1, etc. |
| **TaxCalculationAgent** | Applies 2024 federal tax brackets, standard/itemised deduction choice, Child Tax Credit, EIC |
| **FilingAgent** | Assembles the `FilingPackage`, generates a confirmation number |

### Supported Documents

`W-2` · `1099-NEC` · `1099-INT` · `1099-DIV` · `1099-B` · `1099-R` · `1098` · `Schedule K-1`

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the API server

```bash
uvicorn src.api.app:app --reload
```

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Submit a tax workflow (one API call)

```bash
curl -s -X POST http://localhost:8000/workflows/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_profile": {
      "first_name": "Alice",
      "last_name": "Smith",
      "filing_status": "single",
      "tax_year": 2024,
      "state": "NY"
    },
    "documents": [
      {
        "document_type": "W-2",
        "issuer": "ACME Corp",
        "tax_year": 2024,
        "data": { "wages": 75000, "federal_tax_withheld": 12000 }
      },
      {
        "document_type": "1099-INT",
        "issuer": "Big Bank",
        "tax_year": 2024,
        "data": { "interest_income": 500 }
      }
    ],
    "deductions": {
      "child_tax_credit_eligible_children": 1
    }
  }' | python -m json.tool
```

### 4. Retrieve the filing result

```bash
curl -s http://localhost:8000/workflows/<workflow_id>/result | python -m json.tool
```

---

## Python API

```python
from src.models.tax_models import DocumentType, FilingStatus, TaxDocument, UserProfile
from src.workflows.tax_workflow import TaxWorkflowOrchestrator

orchestrator = TaxWorkflowOrchestrator()
state = orchestrator.run_from_inputs(
    user_profile=UserProfile(
        first_name="Alice", last_name="Smith",
        filing_status=FilingStatus.SINGLE,
        tax_year=2024, state="NY",
    ),
    documents=[
        TaxDocument(
            document_type=DocumentType.W2,
            issuer="ACME Corp",
            data={"wages": 75_000, "federal_tax_withheld": 12_000},
        ),
    ],
)
calc = state.calculation
print(f"Refund / owed: ${calc.refund_or_owed:,.2f}")
print(f"Effective rate: {calc.effective_tax_rate:.1%}")
print(f"Confirmation: {state.filing_package.filing_confirmation}")
```

---

## Project Structure

```
taxinfra/
├── requirements.txt
├── src/
│   ├── agents/
│   │   ├── base_agent.py               # Abstract agent base class
│   │   ├── data_collection_agent.py    # Profile validation & normalisation
│   │   ├── document_processing_agent.py# Document parsing & aggregation
│   │   ├── tax_calculation_agent.py    # Federal tax computation (2024 rules)
│   │   └── filing_agent.py             # Package assembly & confirmation
│   ├── models/
│   │   └── tax_models.py               # Pydantic data models
│   ├── workflows/
│   │   └── tax_workflow.py             # Orchestrator
│   └── api/
│       └── app.py                      # FastAPI application
└── tests/
    ├── test_models.py
    ├── test_agents.py
    ├── test_workflow.py
    └── test_api.py
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

All 50 tests should pass.

---

## REST API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/workflows/` | Create and immediately run a workflow |
| `GET` | `/workflows/{id}` | Get current workflow status and messages |
| `GET` | `/workflows/{id}/result` | Get the completed filing result |
