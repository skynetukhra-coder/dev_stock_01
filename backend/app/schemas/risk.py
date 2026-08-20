"""Risk and Kill switch schemas."""

from __future__ import annotations

from pydantic import BaseModel


class KillSwitchRequest(BaseModel):
    active: bool
    operator_id: str = "operator"
    reason: str = "Emergency toggle"


class KillSwitchResponse(BaseModel):
    active: bool
    message: str


class RiskStatusResponse(BaseModel):
    kill_switch_active: bool
    daily_realized_pnl: float
    daily_unrealized_pnl: float
    open_positions_count: int
    max_open_positions: int
    max_daily_realized_loss: float
    max_daily_total_loss: float
    is_market_open: bool
