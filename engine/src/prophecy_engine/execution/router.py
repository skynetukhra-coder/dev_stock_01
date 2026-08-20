"""Confirmation router, execution modes and manual/automated order routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Sequence

from ..broker.protocols import (
    BrokerOrderResponse,
    OrderExecutionProvider,
    OrderRequest,
    OrderSide,
    OrderType,
)
from ..domain.enums import RiskAction, SignalStatus
from ..domain.models import Signal
from ..domain.state_machine import can_transition
from ..market.sessions import IST, to_ist
from ..risk.manager import RiskContext, RiskEvaluationResult, RiskManager
from ..strategy.option_selector import SelectedContract


class ExecutionMode(str, Enum):
    """Operational mode controlling how strategy signals are processed."""

    SIGNAL_ONLY = "SIGNAL_ONLY"  # Signals created; no orders generated
    MANUAL_CONFIRMATION = "MANUAL_CONFIRMATION"  # Operator must confirm signal before execution
    AUTO_PAPER = "AUTO_PAPER"  # Signals automatically routed to paper broker
    AUTO_LIVE = "AUTO_LIVE"  # Real broker execution (feature-gated)


class RoutingStatus(str, Enum):
    """Status outcomes from ConfirmationRouter routing."""

    ROUTED = "ROUTED"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    RISK_BLOCKED = "RISK_BLOCKED"
    IGNORED = "IGNORED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class RoutingDecision:
    """Audit record of router decision and order placement results."""

    signal_id: str
    mode: ExecutionMode
    status: RoutingStatus
    order_responses: tuple[BrokerOrderResponse, ...] = ()
    risk_result: Optional[RiskEvaluationResult] = None
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(IST))


@dataclass
class _PendingSignal:
    signal: Signal
    contracts: list[SelectedContract]
    context: RiskContext


class ConfirmationRouter:
    """Routes strategy signals through state machine, risk gates, and order providers."""

    def __init__(
        self,
        execution_provider: OrderExecutionProvider,
        risk_manager: Optional[RiskManager] = None,
        default_mode: ExecutionMode = ExecutionMode.MANUAL_CONFIRMATION,
    ) -> None:
        self.execution_provider = execution_provider
        self.risk_manager = risk_manager or RiskManager()
        self.mode = default_mode
        self._pending_signals: dict[str, _PendingSignal] = {}

    def route_signal(
        self,
        signal: Signal,
        contracts: Sequence[SelectedContract],
        context: RiskContext,
        mode: Optional[ExecutionMode] = None,
    ) -> RoutingDecision:
        """Route a newly generated Signal based on the operational ExecutionMode."""
        active_mode = mode or self.mode
        now = to_ist(context.current_time or datetime.now(IST))

        # 1. Live execution safety check
        if active_mode == ExecutionMode.AUTO_LIVE:
            return RoutingDecision(
                signal_id=signal.id,
                mode=active_mode,
                status=RoutingStatus.ERROR,
                message="Live automated execution is disabled by default safety policy",
                timestamp=now,
            )

        # 2. Signal Only Mode
        if active_mode == ExecutionMode.SIGNAL_ONLY:
            self._pending_signals[signal.id] = _PendingSignal(
                signal=signal,
                contracts=list(contracts),
                context=context,
            )
            return RoutingDecision(
                signal_id=signal.id,
                mode=active_mode,
                status=RoutingStatus.WAITING_CONFIRMATION,
                message="Signal queued in SIGNAL_ONLY mode",
                timestamp=now,
            )

        # 3. Manual Confirmation Mode
        if active_mode == ExecutionMode.MANUAL_CONFIRMATION:
            if signal.status != SignalStatus.CONFIRMED:
                self._pending_signals[signal.id] = _PendingSignal(
                    signal=signal,
                    contracts=list(contracts),
                    context=context,
                )
                return RoutingDecision(
                    signal_id=signal.id,
                    mode=active_mode,
                    status=RoutingStatus.WAITING_CONFIRMATION,
                    message="Signal waiting for operator confirmation",
                    timestamp=now,
                )

        # 4. Auto Paper Mode (or confirmed signal)
        return self._execute_contracts(
            signal=signal,
            contracts=contracts,
            context=context,
            mode=active_mode,
            timestamp=now,
        )

    def confirm_signal(
        self,
        signal_id: str,
        operator_id: str = "operator",
    ) -> RoutingDecision:
        """Explicitly confirm a pending signal and trigger order execution."""
        now = datetime.now(IST)
        pending = self._pending_signals.get(signal_id)
        if pending is None:
            return RoutingDecision(
                signal_id=signal_id,
                mode=self.mode,
                status=RoutingStatus.ERROR,
                message=f"Signal {signal_id} not found in pending queue",
                timestamp=now,
            )

        # Validate state machine transition
        if not can_transition(pending.signal.status, SignalStatus.CONFIRMED):
            return RoutingDecision(
                signal_id=signal_id,
                mode=self.mode,
                status=RoutingStatus.ERROR,
                message=f"Cannot transition signal from {pending.signal.status} to CONFIRMED",
                timestamp=now,
            )

        # Remove from pending queue
        del self._pending_signals[signal_id]

        return self._execute_contracts(
            signal=pending.signal,
            contracts=pending.contracts,
            context=pending.context,
            mode=self.mode,
            timestamp=now,
        )

    def ignore_signal(
        self,
        signal_id: str,
        operator_id: str = "operator",
        reason: str = "Operator ignored",
    ) -> bool:
        """Reject/ignore a pending signal."""
        pending = self._pending_signals.get(signal_id)
        if pending is None:
            return False

        if can_transition(pending.signal.status, SignalStatus.IGNORED):
            del self._pending_signals[signal_id]
            return True
        return False

    def _execute_contracts(
        self,
        signal: Signal,
        contracts: Sequence[SelectedContract],
        context: RiskContext,
        mode: ExecutionMode,
        timestamp: datetime,
    ) -> RoutingDecision:
        """Run pre-trade risk checks and submit orders to execution provider."""
        # Risk Gate: check each contract
        for contract in contracts:
            risk_res = self.risk_manager.evaluate_entry(
                signal=signal,
                contract=contract,
                context=context,
            )
            if risk_res.action == RiskAction.BLOCK:
                return RoutingDecision(
                    signal_id=signal.id,
                    mode=mode,
                    status=RoutingStatus.RISK_BLOCKED,
                    risk_result=risk_res,
                    message=f"Order blocked by risk manager: {risk_res.message}",
                    timestamp=timestamp,
                )

        # Order Construction & Placement
        responses: list[BrokerOrderResponse] = []
        for contract in contracts:
            order_req = OrderRequest(
                groww_symbol=contract.groww_symbol,
                side=OrderSide.BUY,
                quantity=contract.quantity,
                order_type=OrderType.MARKET,
                price=contract.ltp,
                tag=signal.id,
            )
            resp = self.execution_provider.place_order(order_req)
            responses.append(resp)

        return RoutingDecision(
            signal_id=signal.id,
            mode=mode,
            status=RoutingStatus.ROUTED,
            order_responses=tuple(responses),
            message=f"Successfully routed {len(responses)} order(s)",
            timestamp=timestamp,
        )
