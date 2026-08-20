"""Pure signal-decision and trade lifecycle state transitions."""

from __future__ import annotations

from .enums import SignalStatus, TradeStatus

# Permitted transitions for Signal decision flow
ALLOWED_SIGNAL_TRANSITIONS: set[tuple[SignalStatus, SignalStatus]] = {
    (SignalStatus.CREATED, SignalStatus.CONFIRMED),
    (SignalStatus.CREATED, SignalStatus.IGNORED),
    (SignalStatus.CREATED, SignalStatus.EXPIRED),
    # Idempotent no-op transitions
    (SignalStatus.CONFIRMED, SignalStatus.CONFIRMED),
    (SignalStatus.IGNORED, SignalStatus.IGNORED),
    (SignalStatus.EXPIRED, SignalStatus.EXPIRED),
}

# Permitted transitions for Trade execution flow
ALLOWED_TRADE_TRANSITIONS: set[tuple[TradeStatus, TradeStatus]] = {
    (TradeStatus.CREATED, TradeStatus.CONFIRMED),
    (TradeStatus.CREATED, TradeStatus.IGNORED),
    (TradeStatus.CREATED, TradeStatus.EXPIRED),
    (TradeStatus.CONFIRMED, TradeStatus.ENTRY_PENDING),
    (TradeStatus.CONFIRMED, TradeStatus.REJECTED),
    (TradeStatus.CONFIRMED, TradeStatus.ERROR),
    (TradeStatus.ENTRY_PENDING, TradeStatus.ENTERED),
    (TradeStatus.ENTRY_PENDING, TradeStatus.PARTIALLY_FILLED),
    (TradeStatus.ENTRY_PENDING, TradeStatus.REJECTED),
    (TradeStatus.ENTRY_PENDING, TradeStatus.ERROR),
    (TradeStatus.PARTIALLY_FILLED, TradeStatus.ENTERED),
    (TradeStatus.PARTIALLY_FILLED, TradeStatus.EXIT_PENDING),
    (TradeStatus.PARTIALLY_FILLED, TradeStatus.EXITED),
    (TradeStatus.PARTIALLY_FILLED, TradeStatus.ERROR),
    (TradeStatus.ENTERED, TradeStatus.EXIT_PENDING),
    (TradeStatus.ENTERED, TradeStatus.EXITED),
    (TradeStatus.ENTERED, TradeStatus.ERROR),
    (TradeStatus.EXIT_PENDING, TradeStatus.EXITED),
    (TradeStatus.EXIT_PENDING, TradeStatus.ERROR),
    # Idempotent transitions
    (TradeStatus.CONFIRMED, TradeStatus.CONFIRMED),
    (TradeStatus.ENTERED, TradeStatus.ENTERED),
    (TradeStatus.EXITED, TradeStatus.EXITED),
    (TradeStatus.IGNORED, TradeStatus.IGNORED),
    (TradeStatus.EXPIRED, TradeStatus.EXPIRED),
    (TradeStatus.REJECTED, TradeStatus.REJECTED),
}


def can_transition(current: SignalStatus, target: SignalStatus) -> bool:
    """Check if a SignalStatus transition is permitted."""
    return (current, target) in ALLOWED_SIGNAL_TRANSITIONS


def can_trade_transition(current: TradeStatus, target: TradeStatus) -> bool:
    """Check if a TradeStatus transition is permitted."""
    return (current, target) in ALLOWED_TRADE_TRANSITIONS
