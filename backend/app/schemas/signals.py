"""Signal request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SignalResponse(BaseModel):
    id: str
    symbol: str
    case_number: int
    created_at: datetime
    status: str
    signal_type: str
    underlying_price: float
    pcr: float
    strategy_version: str = "0.1.0"
    reason: str = ""
    indicators: dict[str, Any] = Field(default_factory=dict)


class SignalListResponse(BaseModel):
    total: int
    signals: list[SignalResponse]


class ConfirmSignalRequest(BaseModel):
    operator_id: str = "operator"
    signature: Optional[str] = None


class IgnoreSignalRequest(BaseModel):
    operator_id: str = "operator"
    reason: str = "Operator ignored"
