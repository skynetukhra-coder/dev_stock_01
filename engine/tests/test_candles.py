import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.market.candles import Candle, CandleSeries, Timeframe


class CandleTests(unittest.TestCase):
    def test_candle_creation_and_fields(self) -> None:
        ts = datetime(2026, 8, 18, 9, 15, tzinfo=timezone.utc)
        candle = Candle(
            timestamp=ts,
            open=100.0,
            high=105.0,
            low=99.5,
            close=103.0,
            volume=5000,
            open_interest=12000,
        )
        self.assertEqual(candle.timestamp, ts)
        self.assertEqual(candle.open, 100.0)
        self.assertEqual(candle.high, 105.0)
        self.assertEqual(candle.low, 99.5)
        self.assertEqual(candle.close, 103.0)
        self.assertEqual(candle.volume, 5000)
        self.assertEqual(candle.open_interest, 12000)

    def test_candle_validation_errors(self) -> None:
        ts = datetime(2026, 8, 18, 9, 15, tzinfo=timezone.utc)
        # Invalid high < low
        with self.assertRaises(ValueError):
            Candle(ts, open=100, high=90, low=95, close=92, volume=100)
        # High < open
        with self.assertRaises(ValueError):
            Candle(ts, open=105, high=100, low=95, close=98, volume=100)
        # Low > close
        with self.assertRaises(ValueError):
            Candle(ts, open=100, high=105, low=98, close=95, volume=100)
        # Negative volume
        with self.assertRaises(ValueError):
            Candle(ts, open=100, high=105, low=95, close=100, volume=-1)
        # Infinite or NaN
        with self.assertRaises(ValueError):
            Candle(ts, open=float("nan"), high=105, low=95, close=100, volume=10)

    def test_timeframe_properties(self) -> None:
        self.assertEqual(Timeframe.M1.minutes, 1)
        self.assertEqual(Timeframe.M3.minutes, 3)
        self.assertEqual(Timeframe.M5.minutes, 5)
        self.assertEqual(Timeframe.M15.minutes, 15)
        self.assertEqual(Timeframe.M30.minutes, 30)
        self.assertEqual(Timeframe.D1.minutes, 375)
        self.assertEqual(Timeframe.from_string("15m"), Timeframe.M15)
        with self.assertRaises(ValueError):
            Timeframe.from_string("2h")

    def test_candle_series_validation_and_properties(self) -> None:
        base_ts = datetime(2026, 8, 18, 9, 15, tzinfo=timezone.utc)
        c1 = Candle(base_ts, 100, 105, 95, 102, 1000)
        c2 = Candle(base_ts + timedelta(minutes=5), 102, 108, 101, 107, 1500)
        c3 = Candle(base_ts + timedelta(minutes=10), 107, 109, 104, 105, 1200)

        series = CandleSeries.create("NIFTY", Timeframe.M5, [c2, c1, c3])  # Out of order input
        self.assertEqual(len(series), 3)
        self.assertEqual(series.timestamps, [c1.timestamp, c2.timestamp, c3.timestamp])
        self.assertEqual(series.opens, [100, 102, 107])
        self.assertEqual(series.highs, [105, 108, 109])
        self.assertEqual(series.lows, [95, 101, 104])
        self.assertEqual(series.closes, [102, 107, 105])
        self.assertEqual(series.volumes, [1000, 1500, 1200])
        self.assertEqual(series.latest, c3)

        # Lookback slice
        sliced = series.slice_lookback(2)
        self.assertEqual(len(sliced), 2)
        self.assertEqual(sliced.candles, (c2, c3))

        # Duplicate timestamp error
        with self.assertRaises(ValueError):
            CandleSeries.create("NIFTY", Timeframe.M5, [c1, c1])


if __name__ == "__main__":
    unittest.main()
