"""Backtest request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    symbol: str = "NIFTY"
    initial_capital: float = 100000.0
    stop_loss_pct: float = 0.20
    take_profit_pct: float = 0.40
    slippage_pct: float = 0.001


class BacktestResponse(BaseModel):
    symbol: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    total_gross_pnl: float
    total_net_pnl: float
    total_costs: float
    max_drawdown_amount: float
    max_drawdown_pct: float
    case_breakdown: dict[int, dict[str, Any]] = Field(default_factory=dict)
    report_markdown: str = ""
