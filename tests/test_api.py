"""Tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app, _workflows
from src.models.tax_models import DocumentType, FilingStatus


@pytest.fixture(autouse=True)
def clear_workflows():
    """Reset in-memory workflow store between tests."""
    _workflows.clear()
    yield
    _workflows.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _simple_payload(
    first_name: str = "Alice",
    last_name: str = "Smith",
    filing_status: str = "single",
    state: str = "NY",
    wages: float = 60_000,
    withheld: float = 9_000,
) -> dict:
    return {
        "user_profile": {
            "first_name": first_name,
            "last_name": last_name,
            "filing_status": filing_status,
            "tax_year": 2024,
            "state": state,
        },
        "documents": [
            {
                "document_type": "W-2",
                "issuer": "ACME Corp",
                "tax_year": 2024,
                "data": {"wages": wages, "federal_tax_withheld": withheld},
            }
        ],
        "deductions": {},
    }


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestCreateWorkflow:
    def test_create_workflow_returns_201(self, client):
        resp = client.post("/workflows/", json=_simple_payload())
        assert resp.status_code == 201

    def test_successful_workflow_status_completed(self, client):
        resp = client.post("/workflows/", json=_simple_payload())
        data = resp.json()
        assert data["status"] == "completed"

    def test_response_contains_workflow_id(self, client):
        resp = client.post("/workflows/", json=_simple_payload())
        data = resp.json()
        assert "workflow_id" in data
        assert len(data["workflow_id"]) > 0

    def test_invalid_profile_returns_failed_status(self, client):
        payload = _simple_payload(first_name="")  # missing first_name
        resp = client.post("/workflows/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "failed"
        assert len(data["errors"]) > 0


class TestGetWorkflow:
    def test_get_existing_workflow(self, client):
        create_resp = client.post("/workflows/", json=_simple_payload())
        wf_id = create_resp.json()["workflow_id"]

        get_resp = client.get(f"/workflows/{wf_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["workflow_id"] == wf_id

    def test_get_nonexistent_workflow_returns_404(self, client):
        resp = client.get("/workflows/nonexistent-id")
        assert resp.status_code == 404


class TestGetResult:
    def test_completed_workflow_returns_result(self, client):
        create_resp = client.post("/workflows/", json=_simple_payload())
        wf_id = create_resp.json()["workflow_id"]

        result_resp = client.get(f"/workflows/{wf_id}/result")
        assert result_resp.status_code == 200
        data = result_resp.json()
        assert data["confirmation"].startswith("TAXINFRA-")
        assert "refund_or_owed" in data
        assert "summary" in data

    def test_failed_workflow_result_returns_409(self, client):
        payload = _simple_payload(first_name="")
        create_resp = client.post("/workflows/", json=payload)
        wf_id = create_resp.json()["workflow_id"]

        result_resp = client.get(f"/workflows/{wf_id}/result")
        assert result_resp.status_code == 409

    def test_result_nonexistent_workflow_returns_404(self, client):
        resp = client.get("/workflows/bad-id/result")
        assert resp.status_code == 404

    def test_summary_fields_present(self, client):
        create_resp = client.post("/workflows/", json=_simple_payload())
        wf_id = create_resp.json()["workflow_id"]
        data = client.get(f"/workflows/{wf_id}/result").json()
        summary = data["summary"]
        for field in [
            "gross_income",
            "adjusted_gross_income",
            "taxable_income",
            "tax_liability",
            "credits",
            "taxes_withheld",
            "effective_tax_rate",
            "marginal_tax_rate",
        ]:
            assert field in summary, f"Missing field: {field}"
