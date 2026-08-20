import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.domain.enums import SignalStatus, SignalType
from prophecy_engine.indicators.engine import IndicatorSnapshot
from prophecy_engine.market.candles import Candle, CandleSeries, Timeframe
from prophecy_engine.strategy import (
    REQUIRED_TIMEFRAMES,
    SignalEngine,
    StrategyConfig,
    evaluate_all_cases,
    evaluate_case_1,
    evaluate_case_2,
    evaluate_case_3,
    evaluate_case_4,
    evaluate_case_5,
    evaluate_case_6,
    validate_timeframe_snapshots,
)


def make_snapshot(
    timeframe: Timeframe,
    rsi: float = 50.0,
    adx: float = 20.0,
    close: float = 24000.0,
) -> IndicatorSnapshot:
    """Create synthetic indicator snapshot for unit testing."""
    return IndicatorSnapshot(
        symbol="NIFTY",
        timeframe=timeframe,
        timestamp=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
        close=close,
        rsi=rsi,
        adx=adx,
        plus_di=25.0,
        minus_di=15.0,
        bollinger_upper=close + 100.0,
        bollinger_middle=close,
        bollinger_lower=close - 100.0,
        bollinger_bandwidth=0.008,
        bollinger_percent_b=0.5,
        psar=close - 50.0,
        psar_trend=1,
        chande_kroll_long=close - 60.0,
        chande_kroll_short=close + 60.0,
        ema_fast=close + 5.0,
        ema_slow=close,
        ema_slope=0.5,
        ema_angle=26.5,
        rvol=1.2,
        vwap=close,
        atr=20.0,
    )


class StrategyCasesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pcr = 1.0

    def _build_snapshots(self, rsi: float, adx: float) -> dict[Timeframe, IndicatorSnapshot]:
        return {tf: make_snapshot(tf, rsi=rsi, adx=adx) for tf in REQUIRED_TIMEFRAMES}

    def test_required_timeframes_completeness(self) -> None:
        self.assertEqual(len(REQUIRED_TIMEFRAMES), 5)
        self.assertEqual(
            REQUIRED_TIMEFRAMES,
            (Timeframe.M1, Timeframe.M3, Timeframe.M5, Timeframe.M15, Timeframe.M30),
        )

    def test_missing_timeframe_guard(self) -> None:
        # Only 4 timeframes provided (30m missing)
        partial = {
            tf: make_snapshot(tf, rsi=50.0, adx=20.0)
            for tf in [Timeframe.M1, Timeframe.M3, Timeframe.M5, Timeframe.M15]
        }
        self.assertFalse(validate_timeframe_snapshots(partial))
        self.assertFalse(evaluate_case_1(partial, self.pcr))
        self.assertIsNone(evaluate_all_cases(partial, self.pcr))

    def test_nan_indicator_guard(self) -> None:
        snaps = self._build_snapshots(rsi=50.0, adx=20.0)
        # Inject NaN into one timeframe
        snaps[Timeframe.M5] = make_snapshot(Timeframe.M5, rsi=float("nan"), adx=20.0)
        self.assertFalse(validate_timeframe_snapshots(snaps))
        self.assertFalse(evaluate_case_1(snaps, self.pcr))
        self.assertIsNone(evaluate_all_cases(snaps, self.pcr))

    def test_case_1_straddle(self) -> None:
        # In-bounds: ADX 20 in [15, 30], RSI 50 in [40, 60]
        snaps = self._build_snapshots(rsi=50.0, adx=20.0)
        self.assertTrue(evaluate_case_1(snaps, self.pcr))

        match = evaluate_all_cases(snaps, self.pcr)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.case_number, 1)
        self.assertEqual(match.signal_type, SignalType.STRADDLE)

        # Boundary checks
        self.assertTrue(evaluate_case_1(self._build_snapshots(40.0, 15.0), self.pcr))
        self.assertTrue(evaluate_case_1(self._build_snapshots(60.0, 30.0), self.pcr))

        # Out-of-bounds
        self.assertFalse(evaluate_case_1(self._build_snapshots(39.0, 20.0), self.pcr))
        self.assertFalse(evaluate_case_1(self._build_snapshots(50.0, 35.0), self.pcr))

    def test_case_2_straddle_special(self) -> None:
        # In-bounds: ADX 5 in [0, 10], RSI 50 in [40, 60]
        snaps = self._build_snapshots(rsi=50.0, adx=5.0)
        self.assertTrue(evaluate_case_2(snaps, self.pcr))

        match = evaluate_all_cases(snaps, self.pcr)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.case_number, 2)
        self.assertEqual(match.signal_type, SignalType.STRADDLE_SPECIAL)

        # Out-of-bounds (ADX > 10)
        self.assertFalse(evaluate_case_2(self._build_snapshots(50.0, 12.0), self.pcr))

    def test_case_3_call(self) -> None:
        # In-bounds: ADX 20 in [15, 30], RSI 45 in [0, 60], PCR 0.70 < 0.8
        snaps = self._build_snapshots(rsi=45.0, adx=20.0)
        self.assertTrue(evaluate_case_3(snaps, pcr=0.70, pcr_threshold=0.8))

        match = evaluate_all_cases(snaps, pcr=0.70)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.case_number, 3)
        self.assertEqual(match.signal_type, SignalType.CALL)

        # PCR out of bounds
        self.assertFalse(evaluate_case_3(snaps, pcr=0.85, pcr_threshold=0.8))

    def test_case_4_put(self) -> None:
        # In-bounds: ADX 20 in [15, 30], RSI 55 in [45, 100], PCR 1.30 > 1.25
        snaps = self._build_snapshots(rsi=55.0, adx=20.0)
        self.assertTrue(evaluate_case_4(snaps, pcr=1.30, pcr_threshold=1.25))

        match = evaluate_all_cases(snaps, pcr=1.30)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.case_number, 4)
        self.assertEqual(match.signal_type, SignalType.PUT)

        # PCR out of bounds
        self.assertFalse(evaluate_case_4(snaps, pcr=1.15, pcr_threshold=1.25))

    def test_case_5_call_special(self) -> None:
        # In-bounds: RSI 20 in [0, 25] (extreme oversold)
        snaps = self._build_snapshots(rsi=20.0, adx=35.0)
        self.assertTrue(evaluate_case_5(snaps, self.pcr))

        match = evaluate_all_cases(snaps, self.pcr)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.case_number, 5)
        self.assertEqual(match.signal_type, SignalType.CALL_SPECIAL)

        # Out-of-bounds (RSI > 25)
        self.assertFalse(evaluate_case_5(self._build_snapshots(26.0, 35.0), self.pcr))

    def test_case_6_put_special(self) -> None:
        # In-bounds: RSI 80 in [70, 100] (extreme overbought)
        snaps = self._build_snapshots(rsi=80.0, adx=35.0)
        self.assertTrue(evaluate_case_6(snaps, self.pcr))

        match = evaluate_all_cases(snaps, self.pcr)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.case_number, 6)
        self.assertEqual(match.signal_type, SignalType.PUT_SPECIAL)

        # Out-of-bounds (RSI < 70)
        self.assertFalse(evaluate_case_6(self._build_snapshots(68.0, 35.0), self.pcr))


class SignalEngineTests(unittest.TestCase):
    def _create_mock_series(self, count: int = 40) -> dict[Timeframe, CandleSeries]:
        base_ts = datetime(2026, 8, 20, 9, 15, tzinfo=timezone.utc)
        result = {}
        for tf in REQUIRED_TIMEFRAMES:
            candles = []
            for i in range(count):
                candles.append(
                    Candle(
                        timestamp=base_ts + timedelta(minutes=tf.minutes * i),
                        open=100.0 + i * 0.5,
                        high=102.0 + i * 0.5,
                        low=99.0 + i * 0.5,
                        close=101.0 + i * 0.5,
                        volume=5000 + i * 100,
                    )
                )
            result[tf] = CandleSeries.create("NIFTY", tf, candles)
        return result

    def test_signal_engine_evaluation(self) -> None:
        engine = SignalEngine()
        multi_tf = self._create_mock_series(count=45)

        signal = engine.evaluate(
            symbol="NIFTY",
            multi_tf_series=multi_tf,
            pcr=0.70,
            underlying_price=24050.0,
        )

        # Even if synthetic trend triggers a case or returns None,
        # it must execute safely without error
        if signal is not None:
            self.assertEqual(signal.symbol, "NIFTY")
            self.assertEqual(signal.status, SignalStatus.CREATED)
            self.assertEqual(signal.underlying_price, 24050.0)
            self.assertTrue(signal.id.startswith("sig-"))
            self.assertIn("1m", signal.indicators)

    def test_disabled_cases_configuration(self) -> None:
        # Disable all cases
        config = StrategyConfig(enabled_cases=())
        engine = SignalEngine(config=config)
        multi_tf = self._create_mock_series(count=45)

        signal = engine.evaluate("NIFTY", multi_tf, pcr=0.70, underlying_price=24050.0)
        self.assertIsNone(signal)


if __name__ == "__main__":
    unittest.main()
