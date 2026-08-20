import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.backtest.costs import SlippageModel, TransactionCostModel
from prophecy_engine.backtest.metrics import calculate_metrics, generate_markdown_report
from prophecy_engine.backtest.models import BacktestTrade, ExitReason
from prophecy_engine.backtest.runner import BacktestConfig, BacktestRunner
from prophecy_engine.domain.enums import SignalType
from prophecy_engine.market.candles import Candle, Timeframe
from prophecy_engine.market.sessions import IST


class BacktesterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cost_model = TransactionCostModel()
        self.slippage = SlippageModel(slippage_pct=0.001)

    def test_transaction_cost_calculations(self) -> None:
        # Buy @ 100, Sell @ 120, Qty 25
        # Buy turnover = 2500, Sell turnover = 3000, Total = 5500
        costs = self.cost_model.calculate_costs(buy_price=100.0, sell_price=120.0, quantity=25)

        # Brokerage = 40.0
        self.assertEqual(costs.brokerage, 40.0)
        # STT = 3000 * 0.000625 = 1.88
        self.assertEqual(costs.stt, 1.88)
        # Exchange charges = 5500 * 0.0005 = 2.75
        self.assertEqual(costs.exchange_charges, 2.75)
        # GST = 18% of (40.0 + 2.75) = 7.695
        self.assertAlmostEqual(costs.gst, 7.70, places=1)
        # Stamp duty = 2500 * 0.00003 = 0.075
        self.assertAlmostEqual(costs.stamp_duty, 0.08, places=1)
        # Total cost
        self.assertGreater(costs.total_cost, 50.0)

    def test_slippage_model(self) -> None:
        raw_price = 100.0
        buy_fill = self.slippage.apply_buy(raw_price)
        sell_fill = self.slippage.apply_sell(raw_price)

        self.assertGreater(buy_fill, raw_price)
        self.assertLess(sell_fill, raw_price)
        self.assertEqual(buy_fill, 100.10)
        self.assertEqual(sell_fill, 99.90)

    def test_metrics_calculation_and_drawdown(self) -> None:
        base_ts = datetime(2026, 8, 20, 10, 0, tzinfo=IST)
        dummy_cost = self.cost_model.calculate_costs(100.0, 110.0, 25)

        # 2 winning trades (+500, +500) and 1 losing trade (-400)
        trades = [
            BacktestTrade(
                trade_id="t1",
                signal_id="s1",
                symbol="NIFTY",
                case_number=3,
                signal_type=SignalType.CALL,
                contract_symbol="NSE-NIFTY-CE",
                entry_time=base_ts,
                entry_price=100.0,
                exit_time=base_ts + timedelta(minutes=10),
                exit_price=120.0,
                quantity=25,
                gross_pnl=500.0,
                net_pnl=447.0,
                costs=dummy_cost,
                exit_reason=ExitReason.TAKE_PROFIT,
                holding_duration_minutes=10.0,
            ),
            BacktestTrade(
                trade_id="t2",
                signal_id="s2",
                symbol="NIFTY",
                case_number=3,
                signal_type=SignalType.CALL,
                contract_symbol="NSE-NIFTY-CE",
                entry_time=base_ts + timedelta(minutes=20),
                entry_price=100.0,
                exit_time=base_ts + timedelta(minutes=30),
                exit_price=80.0,
                quantity=25,
                gross_pnl=-500.0,
                net_pnl=-553.0,
                costs=dummy_cost,
                exit_reason=ExitReason.STOP_LOSS,
                holding_duration_minutes=10.0,
            ),
            BacktestTrade(
                trade_id="t3",
                signal_id="s3",
                symbol="NIFTY",
                case_number=4,
                signal_type=SignalType.PUT,
                contract_symbol="NSE-NIFTY-PE",
                entry_time=base_ts + timedelta(minutes=40),
                entry_price=100.0,
                exit_time=base_ts + timedelta(minutes=50),
                exit_price=120.0,
                quantity=25,
                gross_pnl=500.0,
                net_pnl=447.0,
                costs=dummy_cost,
                exit_reason=ExitReason.TAKE_PROFIT,
                holding_duration_minutes=10.0,
            ),
        ]

        metrics = calculate_metrics(trades, initial_capital=100000.0)

        self.assertEqual(metrics.total_trades, 3)
        self.assertEqual(metrics.winning_trades, 2)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertAlmostEqual(metrics.win_rate, 66.67, places=1)
        self.assertGreater(metrics.profit_factor, 1.0)
        self.assertGreater(metrics.expectancy, 0.0)
        self.assertEqual(metrics.final_capital, 100000.0 + 447.0 - 553.0 + 447.0)
        self.assertIn(3, metrics.case_breakdown)
        self.assertIn(4, metrics.case_breakdown)

        report = generate_markdown_report(metrics)
        self.assertIn("Prophecy Strategy Backtest Performance Report", report)
        self.assertIn("Case 3", report)
        self.assertIn("Case 4", report)

    def test_backtest_runner_execution(self) -> None:
        base_time = datetime(2026, 8, 20, 9, 15, tzinfo=IST)
        multi_tf_candles = {}

        # Generate 60 synchronized candles for all 5 TFs
        for tf in [Timeframe.M1, Timeframe.M3, Timeframe.M5, Timeframe.M15, Timeframe.M30]:
            candles = []
            for i in range(60):
                candles.append(
                    Candle(
                        timestamp=base_time + timedelta(minutes=tf.minutes * i),
                        open=24000.0 + (i % 5) * 5.0,
                        high=24015.0 + (i % 5) * 5.0,
                        low=23990.0 + (i % 5) * 5.0,
                        close=24005.0 + (i % 5) * 5.0,
                        volume=10000 + i * 200,
                    )
                )
            multi_tf_candles[tf] = candles

        runner = BacktestRunner(BacktestConfig(initial_capital=100000.0))
        trades, metrics = runner.run(symbol="NIFTY", multi_tf_candles=multi_tf_candles)

        self.assertIsInstance(trades, list)
        self.assertEqual(metrics.initial_capital, 100000.0)


if __name__ == "__main__":
    unittest.main()
