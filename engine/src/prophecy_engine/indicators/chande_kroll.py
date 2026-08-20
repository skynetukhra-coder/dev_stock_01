"""Chande Kroll Stop volatility trailing bands."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .common import atr


@dataclass(frozen=True)
class ChandeKrollResult:
    """Chande Kroll Stop long and short trailing bands."""

    long_stop: tuple[float, ...]
    short_stop: tuple[float, ...]
    period_p: int
    multiplier_x: float
    period_q: int

    @property
    def latest_long_stop(self) -> float:
        for val in reversed(self.long_stop):
            if math.isfinite(val):
                return val
        return float("nan")

    @property
    def latest_short_stop(self) -> float:
        for val in reversed(self.short_stop):
            if math.isfinite(val):
                return val
        return float("nan")


def calculate_chande_kroll(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period_p: int = 10,
    multiplier_x: float = 1.5,
    period_q: int = 9,
) -> ChandeKrollResult:
    """Calculate Chande Kroll Stop indicator (Long and Short bands)."""
    n = len(highs)
    if not (n == len(lows) == len(closes)):
        raise ValueError("High, low and close sequences must have matching lengths")

    long_stops = [float("nan")] * n
    short_stops = [float("nan")] * n

    if n < period_p + period_q:
        return ChandeKrollResult(
            long_stop=tuple(long_stops),
            short_stop=tuple(short_stops),
            period_p=period_p,
            multiplier_x=multiplier_x,
            period_q=period_q,
        )

    atr_vals = atr(highs, lows, closes, period=period_p)

    # First pass: calculate intermediate high and low stops
    prelim_high_stops = [float("nan")] * n
    prelim_low_stops = [float("nan")] * n

    for i in range(period_p - 1, n):
        max_h = max(highs[i - period_p + 1 : i + 1])
        min_l = min(lows[i - period_p + 1 : i + 1])
        a = atr_vals[i]

        if math.isfinite(a):
            prelim_high_stops[i] = max_h - (multiplier_x * a)
            prelim_low_stops[i] = min_l + (multiplier_x * a)

    # Second pass: smooth over period_q
    start_idx = period_p + period_q - 2
    for i in range(start_idx, n):
        window_high_stops = [
            prelim_high_stops[j]
            for j in range(i - period_q + 1, i + 1)
            if math.isfinite(prelim_high_stops[j])
        ]
        window_low_stops = [
            prelim_low_stops[j]
            for j in range(i - period_q + 1, i + 1)
            if math.isfinite(prelim_low_stops[j])
        ]

        if window_high_stops:
            long_stops[i] = max(window_high_stops)
        if window_low_stops:
            short_stops[i] = min(window_low_stops)

    return ChandeKrollResult(
        long_stop=tuple(long_stops),
        short_stop=tuple(short_stops),
        period_p=period_p,
        multiplier_x=multiplier_x,
        period_q=period_q,
    )
