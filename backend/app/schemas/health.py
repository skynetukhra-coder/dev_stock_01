"""Health response schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "prophecy-backend"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    mode: str = "SIGNAL"
    is_market_open: bool = False
    kill_switch_active: bool = False
