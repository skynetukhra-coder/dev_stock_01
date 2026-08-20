"""Central state and lifecycle service wrapping prophecy_engine."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from prophecy_engine.backtest.metrics import generate_markdown_report
from prophecy_engine.backtest.runner import BacktestConfig, BacktestRunner
from prophecy_engine.broker.protocols import BrokerOrderResponse, Position
from prophecy_engine.domain.enums import SignalStatus
from prophecy_engine.domain.models import Signal
from prophecy_engine.execution.paper import PaperAccount, PaperExecutionEngine
from prophecy_engine.execution.router import (
    ConfirmationRouter,
    ExecutionMode,
    RoutingDecision,
)
from prophecy_engine.market.candles import Candle, Timeframe
from prophecy_engine.market.instruments import InstrumentMaster
from prophecy_engine.market.sessions import IST, is_market_open, to_ist
from prophecy_engine.risk.manager import RiskContext, RiskManager, RiskPolicy
from prophecy_engine.strategy.option_selector import (
    OptionSelectionPolicy,
    OptionSelector,
    SelectedContract,
)
from prophecy_engine.strategy.signal_engine import SignalEngine, StrategyConfig

from .sse_service import event_publisher


class EngineService:
    """Stateful orchestrator for prophecy_engine backend integration."""

    def __init__(self) -> None:
        self.instrument_master = InstrumentMaster()
        self.signal_engine = SignalEngine(StrategyConfig())
        self.option_selector = OptionSelector(OptionSelectionPolicy())
        self.risk_manager = RiskManager(RiskPolicy(enforce_market_hours=False))
        self.paper_account = PaperAccount(initial_cash=500000.0, cash_balance=500000.0)
        self.paper_engine = PaperExecutionEngine(self.paper_account)
        self.router = ConfirmationRouter(
            execution_provider=self.paper_engine,
            risk_manager=self.risk_manager,
            default_mode=ExecutionMode.MANUAL_CONFIRMATION,
        )

        self._signals: dict[str, Signal] = {}
        self._contracts: dict[str, list[SelectedContract]] = {}
        self._orders: list[BrokerOrderResponse] = []

    def get_health(self) -> dict[str, Any]:
        """Query system health, market session and kill switch state."""
        now = datetime.now(IST)
        return {
            "status": "ok",
            "service": "prophecy-backend",
            "timestamp": now,
            "mode": self.router.mode.value,
            "is_market_open": is_market_open(now),
            "kill_switch_active": self.risk_manager.is_kill_switch_active,
        }

    def list_signals(self) -> list[Signal]:
        return sorted(self._signals.values(), key=lambda s: s.created_at, reverse=True)

    def get_signal(self, signal_id: str) -> Optional[Signal]:
        return self._signals.get(signal_id)

    def inject_signal(self, signal: Signal, contracts: list[SelectedContract]) -> RoutingDecision:
        """Register a new signal and route according to ExecutionMode."""
        self._signals[signal.id] = signal
        self._contracts[signal.id] = contracts

        now = to_ist(signal.created_at)
        ctx = RiskContext(
            daily_realized_pnl=self.paper_account.realized_pnl,
            daily_unrealized_pnl=self.paper_account.unrealized_pnl,
            open_positions=self.paper_engine.get_positions(),
            symbol_signal_counts={s.symbol: 1 for s in self._signals.values()},
            recent_signals=list(self._signals.values()),
            current_time=now,
        )

        decision = self.router.route_signal(
            signal=signal,
            contracts=contracts,
            context=ctx,
        )

        if decision.order_responses:
            self._orders.extend(decision.order_responses)

        # Broadcast SSE event
        event_publisher.publish(
            "signal",
            {
                "signal_id": signal.id,
                "symbol": signal.symbol,
                "case_number": signal.case_number,
                "type": signal.signal_type.value,
                "status": signal.status.value,
                "routing_status": decision.status.value,
            },
        )

        return decision

    def confirm_signal(self, signal_id: str, operator_id: str = "operator") -> RoutingDecision:
        """Confirm a pending signal and route orders."""
        decision = self.router.confirm_signal(signal_id, operator_id)
        if signal_id in self._signals and decision.status.value == "ROUTED":
            old_sig = self._signals[signal_id]
            self._signals[signal_id] = Signal(
                id=old_sig.id,
                symbol=old_sig.symbol,
                case_number=old_sig.case_number,
                created_at=old_sig.created_at,
                status=SignalStatus.CONFIRMED,
                signal_type=old_sig.signal_type,
                underlying_price=old_sig.underlying_price,
                pcr=old_sig.pcr,
                strategy_version=old_sig.strategy_version,
                reason=old_sig.reason,
                indicators=old_sig.indicators,
            )

        if decision.order_responses:
            self._orders.extend(decision.order_responses)

        event_publisher.publish(
            "signal_confirmed",
            {
                "signal_id": signal_id,
                "status": decision.status.value,
                "orders_count": len(decision.order_responses),
            },
        )
        return decision

    def ignore_signal(
        self,
        signal_id: str,
        operator_id: str = "operator",
        reason: str = "Operator ignored",
    ) -> bool:
        """Ignore/reject a pending signal."""
        success = self.router.ignore_signal(signal_id, operator_id, reason)
        if success and signal_id in self._signals:
            old_sig = self._signals[signal_id]
            self._signals[signal_id] = Signal(
                id=old_sig.id,
                symbol=old_sig.symbol,
                case_number=old_sig.case_number,
                created_at=old_sig.created_at,
                status=SignalStatus.IGNORED,
                signal_type=old_sig.signal_type,
                underlying_price=old_sig.underlying_price,
                pcr=old_sig.pcr,
                strategy_version=old_sig.strategy_version,
                reason=reason,
                indicators=old_sig.indicators,
            )
            event_publisher.publish("signal_ignored", {"signal_id": signal_id, "reason": reason})
        return success

    def get_orders(self) -> list[BrokerOrderResponse]:
        return list(self._orders)

    def get_positions(self) -> list[Position]:
        return self.paper_engine.get_positions()

    def get_account_summary(self) -> dict[str, float]:
        return self.paper_engine.get_account_summary()

    def toggle_kill_switch(self, active: bool, operator_id: str = "operator") -> bool:
        """Activate or deactivate the emergency kill switch."""
        if active:
            self.risk_manager.activate_kill_switch()
        else:
            self.risk_manager.deactivate_kill_switch()

        event_publisher.publish(
            "kill_switch",
            {"active": active, "operator_id": operator_id, "time": datetime.utcnow().isoformat()},
        )
        return self.risk_manager.is_kill_switch_active

    def run_backtest(
        self,
        symbol: str = "NIFTY",
        initial_capital: float = 100000.0,
        stop_loss_pct: float = 0.20,
        take_profit_pct: float = 0.40,
        slippage_pct: float = 0.001,
    ) -> dict[str, Any]:
        """Execute simulated backtest on synthetic historical multi-TF candles."""
        config = BacktestConfig(
            initial_capital=initial_capital,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            slippage_pct=slippage_pct,
        )
        runner = BacktestRunner(config)

        # Generate synthetic 60 candles per required TF
        base_ts = datetime(2026, 8, 20, 9, 15, tzinfo=IST)
        candles_db = {}
        for tf in [Timeframe.M1, Timeframe.M3, Timeframe.M5, Timeframe.M15, Timeframe.M30]:
            c_list = []
            for i in range(60):
                c_list.append(
                    Candle(
                        timestamp=base_ts + timedelta(minutes=tf.minutes * i),
                        open=24000.0 + (i % 6) * 5.0,
                        high=24015.0 + (i % 6) * 5.0,
                        low=23985.0 + (i % 6) * 5.0,
                        close=24005.0 + (i % 6) * 5.0,
                        volume=15000 + i * 100,
                    )
                )
            candles_db[tf] = c_list

        trades, metrics = runner.run(symbol=symbol, multi_tf_candles=candles_db)
        report_md = generate_markdown_report(metrics)

        return {
            "symbol": symbol,
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "win_rate": metrics.win_rate,
            "profit_factor": metrics.profit_factor,
            "expectancy": metrics.expectancy,
            "total_gross_pnl": metrics.total_gross_pnl,
            "total_net_pnl": metrics.total_net_pnl,
            "total_costs": metrics.total_costs,
            "max_drawdown_amount": metrics.max_drawdown_amount,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "case_breakdown": metrics.case_breakdown,
            "report_markdown": report_md,
        }


# Global singleton instance
engine_service = EngineService()
