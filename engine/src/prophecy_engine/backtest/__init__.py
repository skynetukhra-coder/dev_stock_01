"""Backtesting engine, transaction cost models, and performance metrics."""

from .costs import CostBreakdown, SlippageModel, TransactionCostModel
from .metrics import BacktestMetrics, calculate_metrics, generate_markdown_report
from .models import BacktestTrade, ExitReason
from .runner import BacktestConfig, BacktestRunner

__all__ = [
    "CostBreakdown",
    "TransactionCostModel",
    "SlippageModel",
    "ExitReason",
    "BacktestTrade",
    "BacktestMetrics",
    "calculate_metrics",
    "generate_markdown_report",
    "BacktestConfig",
    "BacktestRunner",
]
