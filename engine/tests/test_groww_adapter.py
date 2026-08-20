import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.broker.groww import GrowwAdapter
from prophecy_engine.broker.mock import MockGrowwAdapter
from prophecy_engine.broker.protocols import (
    MarketDataProvider,
    OrderExecutionProvider,
    OrderRequest,
    OrderSide,
    OrderStatus,
)
from prophecy_engine.config import EngineConfig, GrowwCredentials, TradingMode
from prophecy_engine.market.candles import Timeframe
from prophecy_engine.market.instruments import Exchange, Segment


class GrowwAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_client = MagicMock()
        self.config = EngineConfig(
            trading_mode=TradingMode.SIGNAL,
            strategy_version="0.1.0",
            groww=GrowwCredentials(api_key="test-key", api_secret="test-secret"),
        )
        self.adapter = GrowwAdapter(config=self.config, groww_client=self.mock_client)

    def test_protocols_adherence(self) -> None:
        self.assertTrue(isinstance(self.adapter, MarketDataProvider))
        self.assertTrue(isinstance(self.adapter, OrderExecutionProvider))

    def test_get_historical_candles_parsing(self) -> None:
        self.mock_client.get_historical_candles.return_value = {
            "candles": [
                ["2026-08-18 09:15:00", 24000.0, 24050.0, 23980.0, 24020.0, 15000, 250000],
                ["2026-08-18 09:20:00", 24020.0, 24080.0, 24010.0, 24075.0, 18000, 252000],
            ]
        }

        candles = self.adapter.get_historical_candles(
            exchange=Exchange.NSE,
            segment=Segment.CASH,
            groww_symbol="NSE-NIFTY",
            start_time=datetime(2026, 8, 18, 9, 15, tzinfo=timezone.utc),
            end_time=datetime(2026, 8, 18, 9, 25, tzinfo=timezone.utc),
            timeframe=Timeframe.M5,
        )

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].open, 24000.0)
        self.assertEqual(candles[0].high, 24050.0)
        self.assertEqual(candles[0].low, 23980.0)
        self.assertEqual(candles[0].close, 24020.0)
        self.assertEqual(candles[0].volume, 15000)
        self.assertEqual(candles[0].open_interest, 250000)

    def test_get_quote_parsing(self) -> None:
        self.mock_client.get_quote.return_value = {
            "ltp": 24050.5,
            "open": 24000.0,
            "high": 24100.0,
            "low": 23950.0,
            "close": 23980.0,
            "volume": 50000,
            "open_interest": 1200000,
            "bid": 24050.0,
            "ask": 24051.0,
        }

        quote = self.adapter.get_quote(Exchange.NSE, Segment.CASH, "NSE-NIFTY")
        self.assertEqual(quote.groww_symbol, "NSE-NIFTY")
        self.assertEqual(quote.ltp, 24050.5)
        self.assertEqual(quote.bid, 24050.0)
        self.assertEqual(quote.ask, 24051.0)
        self.assertEqual(quote.volume, 50000)

    def test_get_option_chain_parsing(self) -> None:
        self.mock_client.get_option_chain.return_value = {
            "spot_price": 24000.0,
            "strikes": [
                {
                    "strike_price": 24000.0,
                    "call": {"ltp": 120.0, "open_interest": 45000, "volume": 10000},
                    "put": {"ltp": 115.0, "open_interest": 50000, "volume": 12000},
                }
            ],
        }

        chain = self.adapter.get_option_chain(Exchange.NSE, Segment.FNO, "NIFTY", date(2026, 8, 27))
        self.assertEqual(chain.underlying_symbol, "NIFTY")
        self.assertEqual(chain.underlying_ltp, 24000.0)
        self.assertEqual(len(chain.strikes), 1)
        self.assertEqual(chain.strikes[0].strike_price, 24000.0)
        self.assertEqual(chain.strikes[0].call_ltp, 120.0)
        self.assertEqual(chain.strikes[0].put_ltp, 115.0)

    def test_live_order_safety_gate(self) -> None:
        req = OrderRequest(groww_symbol="NSE-NIFTY", side=OrderSide.BUY, quantity=25)
        # Should raise RuntimeError because trading_mode is SIGNAL
        with self.assertRaises(RuntimeError) as ctx:
            self.adapter.place_order(req)
        self.assertIn("Live broker order execution is prohibited", str(ctx.exception))


class MockGrowwAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_adapter = MockGrowwAdapter()

    def test_mock_order_execution_and_positions(self) -> None:
        req = OrderRequest(
            groww_symbol="NSE-NIFTY26AUG24500CE",
            side=OrderSide.BUY,
            quantity=25,
            price=150.0,
        )
        resp = self.mock_adapter.place_order(req)
        self.assertEqual(resp.status, OrderStatus.FILLED)
        self.assertEqual(resp.filled_quantity, 25)
        self.assertEqual(resp.average_price, 150.0)

        positions = self.mock_adapter.get_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].groww_symbol, "NSE-NIFTY26AUG24500CE")
        self.assertEqual(positions[0].quantity, 25)


if __name__ == "__main__":
    unittest.main()
