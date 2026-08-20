"""Health check endpoint."""

from fastapi import APIRouter

from ..schemas.health import HealthResponse
from ..services.engine_service import engine_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return health, operational mode, market session, and kill switch status."""
    data = engine_service.get_health()
    return HealthResponse(**data)
