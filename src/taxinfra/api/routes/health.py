"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "taxinfra",
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check() -> dict:
    return {
        "status": "ready",
        "components": {
            "audit_trail": "ok",
            "decision_log": "ok",
            "trace_chain": "ok",
            "country_registry": "ok",
        },
    }
