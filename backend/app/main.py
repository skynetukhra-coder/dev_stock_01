"""FastAPI application entrypoint for Prophecy Trading Platform."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    backtest_router,
    health_router,
    orders_router,
    positions_router,
    risk_router,
    signals_router,
    stream_router,
)


def health_payload() -> dict[str, str]:
    """Return the baseline service health representation (M0 backward-compatible)."""
    return {"status": "ok", "service": "prophecy-backend"}


def create_app() -> FastAPI:
    """Create and configure the production FastAPI application."""
    application = FastAPI(
        title="Prophecy Trading Engine API",
        version="0.1.0",
        description="REST and Server-Sent Events API for the Prophecy Options Strategy Engine",
    )

    # CORS configuration for web and mobile clients
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    application.include_router(health_router)
    application.include_router(signals_router)
    application.include_router(orders_router)
    application.include_router(positions_router)
    application.include_router(risk_router)
    application.include_router(backtest_router)
    application.include_router(stream_router)

    return application


app = create_app()
