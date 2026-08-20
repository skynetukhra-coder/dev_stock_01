import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.domain.enums import SignalStatus, SignalType
from prophecy_engine.domain.models import Signal
from prophecy_engine.execution.paper import PaperAccount, PaperExecutionEngine
from prophecy_engine.execution.router import (
    ConfirmationRouter,
    ExecutionMode,
    RoutingStatus,
)
from prophecy_engine.market.instruments import Exchange, OptionType, Segment
from prophecy_engine.market.sessions import IST
from prophecy_engine.risk.manager import RiskContext, RiskManager, RiskPolicy
from prophecy_engine.strategy.option_selector import SelectedContract


class ConfirmationRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 20, 10, 0, tzinfo=IST)
        self.account = PaperAccount(initial_cash=100000.0, cash_balance=100000.0)
        self.paper_engine = PaperExecutionEngine(self.account)
        self.risk_manager = RiskManager(RiskPolicy(enforce_market_hours=False))
        self.router = ConfirmationRouter(
            execution_provider=self.paper_engine,
            risk_manager=self.risk_manager,
            default_mode=ExecutionMode.MANUAL_CONFIRMATION,
        )

        self.signal = Signal(
            id="sig-route-1",
            symbol="NIFTY",
            case_number=3,
            created_at=self.now,
            status=SignalStatus.CREATED,
            signal_type=SignalType.CALL,
            underlying_price=24000.0,
            pcr=0.75,
        )

        self.contract = SelectedContract(
            underlying="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            expiry=date(2026, 8, 27),
            strike=24000.0,
            option_type=OptionType.CE,
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            trading_symbol="NIFTY26AUG24000CE",
            lot_size=25,
            tick_size=0.05,
            ltp=100.0,
            bid=99.5,
            ask=100.5,
            open_interest=50000,
            volume=2000,
            quantity=25,
            num_lots=1,
            selection_reason="Test CE",
        )

        self.context = RiskContext(
            daily_realized_pnl=0.0,
            daily_unrealized_pnl=0.0,
            open_positions=[],
            symbol_signal_counts={},
            recent_signals=[],
            is_broker_healthy=True,
            current_time=self.now,
        )

    def test_signal_only_mode_queues_without_orders(self) -> None:
        dec = self.router.route_signal(
            signal=self.signal,
            contracts=[self.contract],
            context=self.context,
            mode=ExecutionMode.SIGNAL_ONLY,
        )
        self.assertEqual(dec.status, RoutingStatus.WAITING_CONFIRMATION)
        self.assertEqual(len(dec.order_responses), 0)
        self.assertEqual(len(self.paper_engine.get_positions()), 0)

    def test_manual_confirmation_flow(self) -> None:
        # Step 1: Route initial signal (waiting confirmation)
        dec_initial = self.router.route_signal(
            signal=self.signal,
            contracts=[self.contract],
            context=self.context,
            mode=ExecutionMode.MANUAL_CONFIRMATION,
        )
        self.assertEqual(dec_initial.status, RoutingStatus.WAITING_CONFIRMATION)
        self.assertEqual(len(self.paper_engine.get_positions()), 0)

        # Step 2: Confirm signal
        dec_confirmed = self.router.confirm_signal("sig-route-1")
        self.assertEqual(dec_confirmed.status, RoutingStatus.ROUTED)
        self.assertEqual(len(dec_confirmed.order_responses), 1)
        self.assertEqual(len(self.paper_engine.get_positions()), 1)

    def test_auto_paper_mode_immediate_routing(self) -> None:
        dec = self.router.route_signal(
            signal=self.signal,
            contracts=[self.contract],
            context=self.context,
            mode=ExecutionMode.AUTO_PAPER,
        )
        self.assertEqual(dec.status, RoutingStatus.ROUTED)
        self.assertEqual(len(dec.order_responses), 1)
        self.assertEqual(len(self.paper_engine.get_positions()), 1)

    def test_risk_rejection_blocks_routing(self) -> None:
        # Activate kill switch
        self.risk_manager.activate_kill_switch()

        dec = self.router.route_signal(
            signal=self.signal,
            contracts=[self.contract],
            context=self.context,
            mode=ExecutionMode.AUTO_PAPER,
        )
        self.assertEqual(dec.status, RoutingStatus.RISK_BLOCKED)
        self.assertEqual(len(dec.order_responses), 0)
        self.assertEqual(len(self.paper_engine.get_positions()), 0)

    def test_ignore_signal_removes_from_pending(self) -> None:
        self.router.route_signal(
            signal=self.signal,
            contracts=[self.contract],
            context=self.context,
            mode=ExecutionMode.MANUAL_CONFIRMATION,
        )
        ignored = self.router.ignore_signal("sig-route-1")
        self.assertTrue(ignored)

        # Confirmation after ignore should fail
        dec = self.router.confirm_signal("sig-route-1")
        self.assertEqual(dec.status, RoutingStatus.ERROR)


if __name__ == "__main__":
    unittest.main()
