import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.indicators import (
    IndicatorEngine,
    calculate_adx,
    calculate_bollinger_bands,
    calculate_chande_kroll,
    calculate_ema_slope_and_angle,
    calculate_psar,
    calculate_rsi,
    calculate_volume_metrics,
    ema,
    sma,
    standard_deviation,
    true_range,
    wilder_smooth,
)
from prophecy_engine.market.candles import Candle, CandleSeries, Timeframe


class IndicatorTests(unittest.TestCase):
    def test_sma(self) -> None:
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        res = sma(values, period=3)
        self.assertTrue(math.isnan(res[0]))
        self.assertTrue(math.isnan(res[1]))
        self.assertAlmostEqual(res[2], 20.0)  # (10+20+30)/3
        self.assertAlmostEqual(res[3], 30.0)  # (20+30+40)/3
        self.assertAlmostEqual(res[4], 40.0)  # (30+40+50)/3

    def test_ema(self) -> None:
        values = [10.0, 11.0, 12.0, 13.0, 14.0]
        res = ema(values, period=3)
        # alpha = 2/(3+1) = 0.5
        # seed at index 2 is (10+11+12)/3 = 11.0
        self.assertAlmostEqual(res[2], 11.0)
        # index 3: 0.5 * 13 + 0.5 * 11 = 12.0
        self.assertAlmostEqual(res[3], 12.0)
        # index 4: 0.5 * 14 + 0.5 * 12 = 13.0
        self.assertAlmostEqual(res[4], 13.0)

    def test_wilder_smooth(self) -> None:
        values = [10.0, 20.0, 30.0, 40.0]
        res = wilder_smooth(values, period=3)
        # seed at index 2 is (10+20+30)/3 = 20.0
        self.assertAlmostEqual(res[2], 20.0)
        # index 3: (20.0 * 2 + 40.0) / 3 = 80/3 = 26.6666...
        self.assertAlmostEqual(res[3], 80.0 / 3.0)

    def test_standard_deviation(self) -> None:
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        res = standard_deviation(values, period=4)
        # Window [2, 4, 4, 4], mean=3.5, variance = ((2-3.5)^2 + 3*(4-3.5)^2)/4 = 0.75
        self.assertAlmostEqual(res[3], math.sqrt(0.75))

    def test_true_range(self) -> None:
        highs = [100.0, 105.0, 103.0]
        lows = [95.0, 98.0, 92.0]
        closes = [98.0, 102.0, 94.0]
        tr = true_range(highs, lows, closes)
        self.assertAlmostEqual(tr[0], 5.0)  # 100 - 95
        self.assertAlmostEqual(tr[1], 7.0)  # max(105-98=7, |105-98|=7, |98-98|=0)
        self.assertAlmostEqual(tr[2], 11.0)  # max(103-92=11, |103-102|=1, |92-102|=10)

    def test_rsi_constant_up_and_down(self) -> None:
        # Strictly rising
        rising = [float(i) for i in range(1, 30)]
        rsi_up = calculate_rsi(rising, period=14)
        self.assertAlmostEqual(rsi_up.latest, 100.0)

        # Strictly falling
        falling = [float(100 - i) for i in range(30)]
        rsi_down = calculate_rsi(falling, period=14)
        self.assertAlmostEqual(rsi_down.latest, 0.0)

    def test_rsi_reference_values(self) -> None:
        prices = [
            44.34,
            44.09,
            44.15,
            43.61,
            44.33,
            44.83,
            45.10,
            45.42,
            45.84,
            46.08,
            45.89,
            46.03,
            45.61,
            46.28,
            46.28,
            46.00,
            46.03,
        ]
        rsi_res = calculate_rsi(prices, period=14)
        self.assertTrue(math.isfinite(rsi_res.latest))
        self.assertTrue(0.0 <= rsi_res.latest <= 100.0)

    def test_adx_monotonic_trend(self) -> None:
        n = 45
        highs = [100.0 + i * 2.0 for i in range(n)]
        lows = [95.0 + i * 2.0 for i in range(n)]
        closes = [98.0 + i * 2.0 for i in range(n)]

        adx_res = calculate_adx(highs, lows, closes, period=14)
        self.assertTrue(math.isfinite(adx_res.latest_adx))
        self.assertTrue(adx_res.latest_adx > 50.0)  # Strong trend
        self.assertTrue(adx_res.latest_plus_di > adx_res.latest_minus_di)

    def test_bollinger_bands(self) -> None:
        closes = [100.0] * 30
        bb = calculate_bollinger_bands(closes, period=20, multiplier=2.0)
        self.assertAlmostEqual(bb.latest_middle, 100.0)
        self.assertAlmostEqual(bb.latest_upper, 100.0)
        self.assertAlmostEqual(bb.latest_lower, 100.0)
        self.assertAlmostEqual(bb.latest_bandwidth, 0.0)
        self.assertAlmostEqual(bb.latest_percent_b, 0.5)

    def test_psar_trending_and_reversal(self) -> None:
        highs = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 14.0, 12.0, 10.0, 8.0]
        lows = [9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 11.5, 9.5, 7.5, 6.0]
        closes = [9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 12.0, 10.0, 8.0, 6.5]

        psar = calculate_psar(highs, lows, closes)
        self.assertEqual(len(psar.sar), len(highs))
        self.assertTrue(psar.is_bearish)  # Reversed downward at the end

    def test_chande_kroll(self) -> None:
        n = 30
        highs = [100.0 + i for i in range(n)]
        lows = [95.0 + i for i in range(n)]
        closes = [98.0 + i for i in range(n)]

        ck = calculate_chande_kroll(highs, lows, closes, period_p=10, multiplier_x=1.5, period_q=9)
        self.assertTrue(math.isfinite(ck.latest_long_stop))
        self.assertTrue(math.isfinite(ck.latest_short_stop))
        # Long stop should be strictly below current high
        self.assertTrue(ck.latest_long_stop < highs[-1])

    def test_ema_slope_and_angle(self) -> None:
        # Upward sloping series
        closes = [float(100 + i) for i in range(30)]
        res_up = calculate_ema_slope_and_angle(closes, period=10, lookback=1)
        self.assertTrue(res_up.latest_slope > 0.0)
        self.assertTrue(res_up.latest_angle > 0.0)

        # Downward sloping series
        closes_down = [float(200 - i) for i in range(30)]
        res_down = calculate_ema_slope_and_angle(closes_down, period=10, lookback=1)
        self.assertTrue(res_down.latest_slope < 0.0)
        self.assertTrue(res_down.latest_angle < 0.0)

    def test_volume_metrics(self) -> None:
        highs = [100.0] * 25
        lows = [95.0] * 25
        closes = [98.0] * 25
        volumes = [1000] * 20 + [2000] * 5

        vol_res = calculate_volume_metrics(highs, lows, closes, volumes, period=20)
        self.assertTrue(math.isfinite(vol_res.latest_volume_sma))
        self.assertTrue(vol_res.latest_rvol > 1.0)  # 2000 volume is above average
        self.assertAlmostEqual(vol_res.latest_vwap, (100.0 + 95.0 + 98.0) / 3.0)

    def test_indicator_engine_snapshot(self) -> None:
        engine = IndicatorEngine()
        base_ts = datetime(2026, 8, 18, 9, 15, tzinfo=timezone.utc)
        candles = []
        for i in range(40):
            candles.append(
                Candle(
                    timestamp=base_ts + timedelta(minutes=5 * i),
                    open=100.0 + i * 0.5,
                    high=102.0 + i * 0.5,
                    low=99.0 + i * 0.5,
                    close=101.0 + i * 0.5,
                    volume=5000 + i * 100,
                )
            )
        series = CandleSeries.create("NIFTY", Timeframe.M5, candles)
        snapshot = engine.compute_snapshot(series)

        self.assertEqual(snapshot.symbol, "NIFTY")
        self.assertEqual(snapshot.timeframe, Timeframe.M5)
        self.assertTrue(snapshot.is_valid())
        self.assertTrue(0.0 <= snapshot.rsi <= 100.0)
        self.assertTrue(snapshot.adx >= 0.0)
        self.assertTrue(
            snapshot.bollinger_upper >= snapshot.bollinger_middle >= snapshot.bollinger_lower
        )


if __name__ == "__main__":
    unittest.main()
