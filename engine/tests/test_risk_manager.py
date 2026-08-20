import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.broker.protocols import Position
from prophecy_engine.domain.enums import RiskAction, RiskRejectionReason, SignalStatus, SignalType
from prophecy_engine.domain.models import Signal
from prophecy_engine.market.instruments import Exchange, OptionType, Segment
from prophecy_engine.market.sessions import IST
from prophecy_engine.risk.manager import (
    RiskContext,
    RiskManager,
)
from prophecy_engine.strategy.option_selector import SelectedContract, SelectedStraddle


class RiskManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.market_open_time = datetime(2026, 8, 20, 10, 30, tzinfo=IST)  # Thursday 10:30 AM IST
        self.market_closed_time = datetime(2026, 8, 20, 20, 0, tzinfo=IST)  # Thursday 8:00 PM IST
        self.manager = RiskManager()

        self.signal = Signal(
            id="sig-risk-1",
            symbol="NIFTY",
            case_number=3,
            created_at=self.market_open_time,
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
            current_time=self.market_open_time,
        )

    def test_allow_healthy_entry(self) -> None:
        res = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertTrue(res.is_allowed)
        self.assertEqual(res.action, RiskAction.ALLOW)

    def test_kill_switch_blocks_entry_allows_exit(self) -> None:
        self.manager.activate_kill_switch()
        self.assertTrue(self.manager.is_kill_switch_active)

        # Entry blocked
        res_entry = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertFalse(res_entry.is_allowed)
        self.assertIn(RiskRejectionReason.KILL_SWITCH_ACTIVE, res_entry.reasons)

        # Exit allowed
        dummy_pos = Position("NSE-NIFTY-2026-08-27-24000-CE", 25, 100.0, 105.0, 125.0)
        res_exit = self.manager.evaluate_exit(dummy_pos, self.context)
        self.assertTrue(res_exit.is_allowed)

        # Deactivate
        self.manager.deactivate_kill_switch()
        self.assertFalse(self.manager.is_kill_switch_active)
        self.assertTrue(
            self.manager.evaluate_entry(self.signal, self.contract, self.context).is_allowed
        )

    def test_max_daily_realized_loss_limit(self) -> None:
        self.context.daily_realized_pnl = -12000.0  # Limit is 10000.0
        res = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertFalse(res.is_allowed)
        self.assertIn(RiskRejectionReason.MAX_DAILY_LOSS_EXCEEDED, res.reasons)

    def test_max_daily_total_loss_limit(self) -> None:
        self.context.daily_realized_pnl = -8000.0
        self.context.daily_unrealized_pnl = -8000.0  # Total = -16000 (Limit is 15000.0)
        res = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertFalse(res.is_allowed)
        self.assertIn(RiskRejectionReason.MAX_DAILY_LOSS_EXCEEDED, res.reasons)

    def test_max_open_positions_limit(self) -> None:
        # Limit is 5 positions
        self.context.open_positions = [
            Position(f"POS-{i}", 25, 100.0, 100.0, 0.0) for i in range(5)
        ]
        res = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertFalse(res.is_allowed)
        self.assertIn(RiskRejectionReason.MAX_OPEN_POSITIONS_REACHED, res.reasons)

    def test_trade_notional_limit(self) -> None:
        # Contract notional = 2500 * 25 = 62,500 (Limit is 50,000)
        expensive_contract = SelectedContract(
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
            ltp=2500.0,
            bid=2490.0,
            ask=2510.0,
            open_interest=50000,
            volume=2000,
            quantity=25,
            num_lots=1,
            selection_reason="Expensive CE",
        )
        res = self.manager.evaluate_entry(self.signal, expensive_contract, self.context)
        self.assertFalse(res.is_allowed)
        self.assertIn(RiskRejectionReason.MAX_TRADE_NOTIONAL_EXCEEDED, res.reasons)

    def test_duplicate_signal_cooldown(self) -> None:
        prev_signal = Signal(
            id="sig-prev",
            symbol="NIFTY",
            case_number=3,
            created_at=self.market_open_time - timedelta(seconds=60),  # 60s ago (< 300s cooldown)
            status=SignalStatus.CREATED,
            signal_type=SignalType.CALL,
        )
        self.context.recent_signals = [prev_signal]

        res = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertFalse(res.is_allowed)
        self.assertIn(RiskRejectionReason.DUPLICATE_SIGNAL_LOCKED, res.reasons)

    def test_symbol_session_frequency_limit(self) -> None:
        self.context.symbol_signal_counts = {"NIFTY": 5}  # Limit is 5
        res = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertFalse(res.is_allowed)
        self.assertIn(RiskRejectionReason.SYMBOL_SESSION_LIMIT_REACHED, res.reasons)

    def test_market_closed_enforcement(self) -> None:
        self.context.current_time = self.market_closed_time
        res = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertFalse(res.is_allowed)
        self.assertIn(RiskRejectionReason.MARKET_CLOSED, res.reasons)

    def test_broker_unhealthy(self) -> None:
        self.context.is_broker_healthy = False
        res = self.manager.evaluate_entry(self.signal, self.contract, self.context)
        self.assertFalse(res.is_allowed)
        self.assertIn(RiskRejectionReason.BROKER_UNHEALTHY, res.reasons)

    def test_straddle_risk_evaluation(self) -> None:
        pe_contract = SelectedContract(
            underlying="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            expiry=date(2026, 8, 27),
            strike=24000.0,
            option_type=OptionType.PE,
            groww_symbol="NSE-NIFTY-2026-08-27-24000-PE",
            trading_symbol="NIFTY26AUG24000PE",
            lot_size=25,
            tick_size=0.05,
            ltp=100.0,
            bid=99.5,
            ask=100.5,
            open_interest=50000,
            volume=2000,
            quantity=25,
            num_lots=1,
            selection_reason="Test PE",
        )
        straddle = SelectedStraddle(
            underlying="NIFTY",
            expiry=date(2026, 8, 27),
            strike=24000.0,
            call_contract=self.contract,
            put_contract=pe_contract,
            combined_premium=200.0,
            selection_reason="ATM Straddle",
        )
        res = self.manager.evaluate_straddle_entry(self.signal, straddle, self.context)
        self.assertTrue(res.is_allowed)


if __name__ == "__main__":
    unittest.main()
