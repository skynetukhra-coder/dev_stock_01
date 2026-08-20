"""Execution layer: paper trading, confirmation router, and live safety gate."""

from .live_gate import (
    ConfirmationToken,
    LiveBrokerAdapter,
    LiveOrderValidationResult,
    LiveSafetyConfig,
    LiveSafetyGate,
    LiveTradingDisabledError,
)
from .paper import PaperAccount, PaperExecutionEngine
from .router import (
    ConfirmationRouter,
    ExecutionMode,
    RoutingDecision,
    RoutingStatus,
)

__all__ = [
    "PaperAccount",
    "PaperExecutionEngine",
    "ConfirmationRouter",
    "ExecutionMode",
    "RoutingDecision",
    "RoutingStatus",
    "ConfirmationToken",
    "LiveSafetyGate",
    "LiveSafetyConfig",
    "LiveBrokerAdapter",
    "LiveTradingDisabledError",
    "LiveOrderValidationResult",
]
