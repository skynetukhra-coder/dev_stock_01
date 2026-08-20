"""Parabolic Stop and Reverse (PSAR) indicator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PSARResult:
    """Parabolic SAR calculation output."""

    sar: tuple[float, ...]
    trend: tuple[int, ...]  # +1 for Bullish (SAR below price), -1 for Bearish (SAR above price)
    af_start: float
    af_step: float
    af_max: float

    @property
    def latest_sar(self) -> float:
        for val in reversed(self.sar):
            if math.isfinite(val):
                return val
        return float("nan")

    @property
    def latest_trend(self) -> int:
        for val in reversed(self.trend):
            if val != 0:
                return val
        return 0

    @property
    def is_bullish(self) -> bool:
        return self.latest_trend == 1

    @property
    def is_bearish(self) -> bool:
        return self.latest_trend == -1


def calculate_psar(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    af_start: float = 0.02,
    af_step: float = 0.02,
    af_max: float = 0.2,
) -> PSARResult:
    """Calculate Parabolic Stop and Reverse (PSAR) according to Wilder's rules."""
    n = len(highs)
    if not (n == len(lows) == len(closes)):
        raise ValueError("High, low, and close sequences must have matching lengths")

    sar = [float("nan")] * n
    trend = [0] * n

    if n < 2:
        return PSARResult(
            sar=tuple(sar),
            trend=tuple(trend),
            af_start=af_start,
            af_step=af_step,
            af_max=af_max,
        )

    # Initialize trend from first two bars
    if closes[1] >= closes[0]:
        is_bull = True
        sar[1] = lows[0]
        ep = highs[1]
        trend[1] = 1
    else:
        is_bull = False
        sar[1] = highs[0]
        ep = lows[1]
        trend[1] = -1

    af = af_start

    for i in range(2, n):
        prev_sar = sar[i - 1]

        if is_bull:
            curr_sar = prev_sar + af * (ep - prev_sar)
            # SAR cannot be higher than the low of the previous two bars
            curr_sar = min(curr_sar, lows[i - 1], lows[i - 2])

            # Check reversal
            if lows[i] < curr_sar:
                is_bull = False
                curr_sar = ep  # SAR jumps to highest high of uptrend
                ep = lows[i]
                af = af_start
                trend[i] = -1
            else:
                trend[i] = 1
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + af_step, af_max)

            sar[i] = curr_sar

        else:  # Bearish
            curr_sar = prev_sar + af * (ep - prev_sar)
            # SAR cannot be lower than the high of the previous two bars
            curr_sar = max(curr_sar, highs[i - 1], highs[i - 2])

            # Check reversal
            if highs[i] > curr_sar:
                is_bull = True
                curr_sar = ep  # SAR jumps to lowest low of downtrend
                ep = highs[i]
                af = af_start
                trend[i] = 1
            else:
                trend[i] = -1
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + af_step, af_max)

            sar[i] = curr_sar

    return PSARResult(
        sar=tuple(sar),
        trend=tuple(trend),
        af_start=af_start,
        af_step=af_step,
        af_max=af_max,
    )
