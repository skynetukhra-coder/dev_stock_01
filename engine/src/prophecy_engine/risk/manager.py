"""Authoritative Risk Manager, Portfolio Controls, and Emergency Kill Switch."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..broker.protocols import Position
from ..domain.enums import RiskAction, RiskRejectionReason
from ..domain.models import Signal
from ..market.sessions import IST, is_market_open, to_ist
from ..strategy.option_selector import SelectedContract, SelectedStraddle


@dataclass(frozen=True)
class RiskPolicy:
    """Configurable risk parameters enforced authoritatively by the engine."""

    max_daily_realized_loss: float = 10000.0
    max_daily_total_loss: float = 15000.0  # Realized + open unrealized P&L
    max_open_positions: int = 5
    max_exposure_per_underlying: float = 200000.0
    max_trade_notional: float = 50000.0
    max_signals_per_symbol_per_day: int = 5
    duplicate_cooldown_seconds: int = 300  # 5 minutes
    max_allowed_slippage_pct: float = 0.03  # 3%
    enforce_market_hours: bool = True
    manual_mode: bool = True


@dataclass
class RiskContext:
    """Live state of portfolio, open positions, daily P&L and recent events."""

    daily_realized_pnl: float = 0.0
    daily_unrealized_pnl: float = 0.0
    open_positions: list[Position] = field(default_factory=list)
    symbol_signal_counts: dict[str, int] = field(default_factory=dict)
    recent_signals: list[Signal] = field(default_factory=list)
    is_broker_healthy: bool = True
    current_time: Optional[datetime] = None


@dataclass(frozen=True)
class RiskEvaluationResult:
    """Result of risk evaluation containing decision and any rejection reasons."""

    action: RiskAction
    reasons: tuple[RiskRejectionReason, ...] = ()
    message: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.action == RiskAction.ALLOW


class RiskManager:
    """Enforces authoritative pre-trade, portfolio, and session risk rules."""

    def __init__(self, default_policy: Optional[RiskPolicy] = None) -> None:
        self.default_policy = default_policy or RiskPolicy()
        self._kill_switch_active: bool = False

    @property
    def is_kill_switch_active(self) -> bool:
        return self._kill_switch_active

    def activate_kill_switch(self) -> None:
        """Emergency stop: block all new entry orders immediately."""
        self._kill_switch_active = True

    def deactivate_kill_switch(self) -> None:
        """Resume normal risk evaluation."""
        self._kill_switch_active = False

    def evaluate_entry(
        self,
        signal: Signal,
        contract: SelectedContract,
        context: RiskContext,
        policy: Optional[RiskPolicy] = None,
    ) -> RiskEvaluationResult:
        """Evaluate single-leg contract entry against all risk controls."""
        active_policy = policy or self.default_policy
        now = to_ist(context.current_time or datetime.now(IST))
        reasons: list[RiskRejectionReason] = []
        messages: list[str] = []

        # 1. Kill Switch Check
        if self._kill_switch_active:
            reasons.append(RiskRejectionReason.KILL_SWITCH_ACTIVE)
            messages.append("Emergency kill switch is active")

        # 2. Broker Health Check
        if not context.is_broker_healthy:
            reasons.append(RiskRejectionReason.BROKER_UNHEALTHY)
            messages.append("Broker connection is unhealthy or degraded")

        # 3. Market Session Check
        if active_policy.enforce_market_hours and not is_market_open(now):
            reasons.append(RiskRejectionReason.MARKET_CLOSED)
            messages.append("Market is closed for regular trading")

        # 4. Daily Realized Loss Limit
        if context.daily_realized_pnl < -active_policy.max_daily_realized_loss:
            reasons.append(RiskRejectionReason.MAX_DAILY_LOSS_EXCEEDED)
            messages.append(
                f"Realized loss ({context.daily_realized_pnl:.2f}) exceeds max "
                f"({active_policy.max_daily_realized_loss:.2f})"
            )

        # 5. Daily Total Loss Limit (Realized + Unrealized)
        total_pnl = context.daily_realized_pnl + context.daily_unrealized_pnl
        if total_pnl < -active_policy.max_daily_total_loss:
            reasons.append(RiskRejectionReason.MAX_DAILY_LOSS_EXCEEDED)
            messages.append(
                f"Total daily loss ({total_pnl:.2f}) exceeds max total loss limit "
                f"({active_policy.max_daily_total_loss:.2f})"
            )

        # 6. Max Open Positions Limit
        if len(context.open_positions) >= active_policy.max_open_positions:
            reasons.append(RiskRejectionReason.MAX_OPEN_POSITIONS_REACHED)
            messages.append(
                f"Open position count ({len(context.open_positions)}) reached max limit "
                f"({active_policy.max_open_positions})"
            )

        # 7. Trade Notional Limit
        trade_notional = contract.ltp * contract.quantity
        if trade_notional > active_policy.max_trade_notional:
            reasons.append(RiskRejectionReason.MAX_TRADE_NOTIONAL_EXCEEDED)
            messages.append(
                f"Trade notional ({trade_notional:.2f}) exceeds single-trade max "
                f"({active_policy.max_trade_notional:.2f})"
            )

        # 8. Exposure Limit by Underlying
        curr_underlying_exp = sum(
            abs(p.quantity * p.ltp)
            for p in context.open_positions
            if contract.underlying in p.groww_symbol
        )
        total_und_exp = curr_underlying_exp + trade_notional
        if total_und_exp > active_policy.max_exposure_per_underlying:
            reasons.append(RiskRejectionReason.MAX_UNDERLYING_EXPOSURE_EXCEEDED)
            msg = (
                f"Total exposure for {contract.underlying} ({total_und_exp:.2f}) "
                f"exceeds max limit ({active_policy.max_exposure_per_underlying:.2f})"
            )
            messages.append(msg)

        # 9. Symbol Session Frequency Limit
        sym_count = context.symbol_signal_counts.get(signal.symbol, 0)
        max_sym_sig = active_policy.max_signals_per_symbol_per_day
        if sym_count >= max_sym_sig:
            reasons.append(RiskRejectionReason.SYMBOL_SESSION_LIMIT_REACHED)
            messages.append(
                f"Symbol {signal.symbol} reached session limit ({sym_count}/{max_sym_sig})"
            )

        # 10. Duplicate Signal Cooldown Lock
        for prev in context.recent_signals:
            if (
                prev.id != signal.id
                and prev.symbol == signal.symbol
                and prev.case_number == signal.case_number
            ):
                elapsed = (now - to_ist(prev.created_at)).total_seconds()
                if 0 <= elapsed < active_policy.duplicate_cooldown_seconds:
                    reasons.append(RiskRejectionReason.DUPLICATE_SIGNAL_LOCKED)
                    cd_sec = active_policy.duplicate_cooldown_seconds
                    msg = (
                        f"Duplicate signal for {signal.symbol} Case {signal.case_number} "
                        f"within cooldown window ({int(elapsed)}s < {cd_sec}s)"
                    )
                    messages.append(msg)
                    break

        if reasons:
            return RiskEvaluationResult(
                action=RiskAction.BLOCK,
                reasons=tuple(reasons),
                message="; ".join(messages),
            )

        return RiskEvaluationResult(
            action=RiskAction.ALLOW,
            message="Trade passed all risk checks",
        )

    def evaluate_straddle_entry(
        self,
        signal: Signal,
        straddle: SelectedStraddle,
        context: RiskContext,
        policy: Optional[RiskPolicy] = None,
    ) -> RiskEvaluationResult:
        """Evaluate dual-leg straddle entry combining CE and PE leg risk."""
        active_policy = policy or self.default_policy
        now = to_ist(context.current_time or datetime.now(IST))
        reasons: list[RiskRejectionReason] = []
        messages: list[str] = []

        if self._kill_switch_active:
            reasons.append(RiskRejectionReason.KILL_SWITCH_ACTIVE)
            messages.append("Emergency kill switch is active")

        if not context.is_broker_healthy:
            reasons.append(RiskRejectionReason.BROKER_UNHEALTHY)
            messages.append("Broker connection is unhealthy")

        if active_policy.enforce_market_hours and not is_market_open(now):
            reasons.append(RiskRejectionReason.MARKET_CLOSED)
            messages.append("Market is closed")

        total_straddle_notional = (
            straddle.call_contract.ltp * straddle.call_contract.quantity
            + straddle.put_contract.ltp * straddle.put_contract.quantity
        )
        if total_straddle_notional > active_policy.max_trade_notional:
            reasons.append(RiskRejectionReason.MAX_TRADE_NOTIONAL_EXCEEDED)
            messages.append(
                f"Combined straddle notional ({total_straddle_notional:.2f}) "
                f"exceeds limit ({active_policy.max_trade_notional:.2f})"
            )

        # Positions count check (straddle uses 2 positions)
        if len(context.open_positions) + 2 > active_policy.max_open_positions:
            reasons.append(RiskRejectionReason.MAX_OPEN_POSITIONS_REACHED)
            messages.append("Adding straddle exceeds max open positions limit")

        if reasons:
            return RiskEvaluationResult(
                action=RiskAction.BLOCK,
                reasons=tuple(reasons),
                message="; ".join(messages),
            )

        return RiskEvaluationResult(
            action=RiskAction.ALLOW, message="Straddle passed all risk checks"
        )

    def evaluate_exit(self, position: Position, context: RiskContext) -> RiskEvaluationResult:
        """Evaluate position exit. Risk-reducing exits are unconditionally allowed."""
        return RiskEvaluationResult(
            action=RiskAction.ALLOW,
            message="Position exit is always permitted to reduce risk",
        )
