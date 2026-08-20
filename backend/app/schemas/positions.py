"""Position and Account summary schemas."""

from __future__ import annotations

from pydantic import BaseModel


class PositionModel(BaseModel):
    groww_symbol: str
    quantity: int
    average_price: float
    ltp: float
    pnl: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0


class AccountSummaryResponse(BaseModel):
    initial_cash: float
    cash_balance: float
    portfolio_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
