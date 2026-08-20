"""Backtesting trade records and lifecycle definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..domain.enums import SignalType
from .costs import CostBreakdown


class ExitReason(str, Enum):
    """Reason for terminating a backtested position."""

    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    OPPOSITE_SIGNAL = "OPPOSITE_SIGNAL"
    TIME_STOP = "TIME_STOP"
    SESSION_END = "SESSION_END"
    KILL_SWITCH = "KILL_SWITCH"


@dataclass(frozen=True)
class BacktestTrade:
    """Individual trade execution record in backtest simulation."""

    trade_id: str
    signal_id: str
    symbol: str
    case_number: int
    signal_type: SignalType
    contract_symbol: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: int
    gross_pnl: float
    net_pnl: float
    costs: CostBreakdown
    exit_reason: ExitReason
    holding_duration_minutes: float

    @property
    def is_winner(self) -> bool:
        return self.net_pnl > 0.0
