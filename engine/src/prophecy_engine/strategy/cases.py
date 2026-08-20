"""Pure evaluation functions for Strategy Cases 1 through 6."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from ..domain.enums import SignalType
from ..indicators.engine import IndicatorSnapshot
from ..market.candles import Timeframe

# Mandatory five-timeframe universe for all multi-timeframe strategy cases
REQUIRED_TIMEFRAMES: tuple[Timeframe, ...] = (
    Timeframe.M1,
    Timeframe.M3,
    Timeframe.M5,
    Timeframe.M15,
    Timeframe.M30,
)


@dataclass(frozen=True)
class CaseMatch:
    """Result of a matching strategy case evaluation."""

    case_number: int
    signal_type: SignalType
    reason: str


def validate_timeframe_snapshots(
    snapshots: Mapping[Timeframe, IndicatorSnapshot],
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES,
) -> bool:
    """Validate that all required timeframes exist and carry valid indicator numbers."""
    if not all(tf in snapshots for tf in required_timeframes):
        return False
    return all(snapshots[tf].is_valid() for tf in required_timeframes)


def evaluate_case_1(
    snapshots: Mapping[Timeframe, IndicatorSnapshot],
    pcr: float,
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES,
) -> bool:
    """Case 1 (Straddle): ADX 15-30 and RSI 40-60 across all required timeframes."""
    if not validate_timeframe_snapshots(snapshots, required_timeframes):
        return False
    return all(
        15.0 <= snapshots[tf].adx <= 30.0 and 40.0 <= snapshots[tf].rsi <= 60.0
        for tf in required_timeframes
    )


def evaluate_case_2(
    snapshots: Mapping[Timeframe, IndicatorSnapshot],
    pcr: float,
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES,
) -> bool:
    """Case 2 (Straddle Special): ADX 0-10 and RSI 40-60 across all required timeframes."""
    if not validate_timeframe_snapshots(snapshots, required_timeframes):
        return False
    return all(
        0.0 <= snapshots[tf].adx <= 10.0 and 40.0 <= snapshots[tf].rsi <= 60.0
        for tf in required_timeframes
    )


def evaluate_case_3(
    snapshots: Mapping[Timeframe, IndicatorSnapshot],
    pcr: float,
    pcr_threshold: float = 0.8,
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES,
) -> bool:
    """Case 3 (Call): ADX 15-30, RSI 0-60 across all timeframes and PCR < 0.8."""
    if not validate_timeframe_snapshots(snapshots, required_timeframes):
        return False
    if not (pcr < pcr_threshold):
        return False
    return all(
        15.0 <= snapshots[tf].adx <= 30.0 and 0.0 <= snapshots[tf].rsi <= 60.0
        for tf in required_timeframes
    )


def evaluate_case_4(
    snapshots: Mapping[Timeframe, IndicatorSnapshot],
    pcr: float,
    pcr_threshold: float = 1.25,
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES,
) -> bool:
    """Case 4 (Put): ADX 15-30, RSI 45-100 across all timeframes and PCR > 1.25."""
    if not validate_timeframe_snapshots(snapshots, required_timeframes):
        return False
    if not (pcr > pcr_threshold):
        return False
    return all(
        15.0 <= snapshots[tf].adx <= 30.0 and 45.0 <= snapshots[tf].rsi <= 100.0
        for tf in required_timeframes
    )


def evaluate_case_5(
    snapshots: Mapping[Timeframe, IndicatorSnapshot],
    pcr: float,
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES,
) -> bool:
    """Case 5 (Call Special): RSI 0-25 (extreme oversold) across all required timeframes."""
    if not validate_timeframe_snapshots(snapshots, required_timeframes):
        return False
    return all(0.0 <= snapshots[tf].rsi <= 25.0 for tf in required_timeframes)


def evaluate_case_6(
    snapshots: Mapping[Timeframe, IndicatorSnapshot],
    pcr: float,
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES,
) -> bool:
    """Case 6 (Put Special): RSI 70-100 (extreme overbought) across all required timeframes."""
    if not validate_timeframe_snapshots(snapshots, required_timeframes):
        return False
    return all(70.0 <= snapshots[tf].rsi <= 100.0 for tf in required_timeframes)


def evaluate_all_cases(
    snapshots: Mapping[Timeframe, IndicatorSnapshot],
    pcr: float,
    call_pcr_max: float = 0.8,
    put_pcr_min: float = 1.25,
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES,
) -> Optional[CaseMatch]:
    """Evaluate all six cases in priority order and return first match, or None."""
    if not validate_timeframe_snapshots(snapshots, required_timeframes):
        return None

    # Priority 1: Extreme contrarian cases (Case 5 & Case 6)
    if evaluate_case_5(snapshots, pcr, required_timeframes):
        return CaseMatch(
            case_number=5,
            signal_type=SignalType.CALL_SPECIAL,
            reason="Case 5: Call Special (RSI <= 25 extreme oversold on all timeframes)",
        )

    if evaluate_case_6(snapshots, pcr, required_timeframes):
        return CaseMatch(
            case_number=6,
            signal_type=SignalType.PUT_SPECIAL,
            reason="Case 6: Put Special (RSI >= 70 extreme overbought on all timeframes)",
        )

    # Priority 2: Directional momentum cases (Case 3 & Case 4)
    if evaluate_case_3(snapshots, pcr, call_pcr_max, required_timeframes):
        return CaseMatch(
            case_number=3,
            signal_type=SignalType.CALL,
            reason=f"Case 3: Call (ADX 15-30, RSI 0-60, PCR {pcr:.2f} < {call_pcr_max})",
        )

    if evaluate_case_4(snapshots, pcr, put_pcr_min, required_timeframes):
        return CaseMatch(
            case_number=4,
            signal_type=SignalType.PUT,
            reason=f"Case 4: Put (ADX 15-30, RSI 45-100, PCR {pcr:.2f} > {put_pcr_min})",
        )

    # Priority 3: Non-directional / Consolidation straddles (Case 1 & Case 2)
    if evaluate_case_1(snapshots, pcr, required_timeframes):
        return CaseMatch(
            case_number=1,
            signal_type=SignalType.STRADDLE,
            reason="Case 1: Straddle (ADX 15-30, RSI 40-60 on all timeframes)",
        )

    if evaluate_case_2(snapshots, pcr, required_timeframes):
        return CaseMatch(
            case_number=2,
            signal_type=SignalType.STRADDLE_SPECIAL,
            reason="Case 2: Straddle Special (ADX 0-10, RSI 40-60 on all timeframes)",
        )

    return None
