"""Bollinger Bands, Bandwidth and %B (percent_b) indicators."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .common import sma, standard_deviation


@dataclass(frozen=True)
class BollingerBandsResult:
    """Bollinger Bands calculation series and latest metrics."""

    upper: tuple[float, ...]
    middle: tuple[float, ...]
    lower: tuple[float, ...]
    bandwidth: tuple[float, ...]
    percent_b: tuple[float, ...]
    period: int
    multiplier: float

    @property
    def latest_upper(self) -> float:
        return self._latest(self.upper)

    @property
    def latest_middle(self) -> float:
        return self._latest(self.middle)

    @property
    def latest_lower(self) -> float:
        return self._latest(self.lower)

    @property
    def latest_bandwidth(self) -> float:
        return self._latest(self.bandwidth)

    @property
    def latest_percent_b(self) -> float:
        return self._latest(self.percent_b)

    @staticmethod
    def _latest(series: tuple[float, ...]) -> float:
        for val in reversed(series):
            if math.isfinite(val):
                return val
        return float("nan")


def calculate_bollinger_bands(
    closes: Sequence[float],
    period: int = 20,
    multiplier: float = 2.0,
) -> BollingerBandsResult:
    """Calculate Bollinger Bands (Upper, Middle, Lower, Bandwidth, and %B)."""
    if period <= 0:
        raise ValueError(f"Period must be positive, got {period}")
    if multiplier < 0:
        raise ValueError(f"Multiplier cannot be negative, got {multiplier}")

    n = len(closes)
    mid = sma(closes, period)
    stdev = standard_deviation(closes, period)

    upper = [float("nan")] * n
    lower = [float("nan")] * n
    bandwidth = [float("nan")] * n
    percent_b = [float("nan")] * n

    for i in range(period - 1, n):
        m = mid[i]
        sd = stdev[i]
        up = m + (multiplier * sd)
        lo = m - (multiplier * sd)
        upper[i] = up
        lower[i] = lo

        # Bandwidth = (Upper - Lower) / Middle
        if m != 0:
            bandwidth[i] = (up - lo) / m
        else:
            bandwidth[i] = 0.0

        # %B = (Price - Lower) / (Upper - Lower)
        band_span = up - lo
        if band_span > 0:
            percent_b[i] = (closes[i] - lo) / band_span
        else:
            percent_b[i] = 0.5

    return BollingerBandsResult(
        upper=tuple(upper),
        middle=tuple(mid),
        lower=tuple(lower),
        bandwidth=tuple(bandwidth),
        percent_b=tuple(percent_b),
        period=period,
        multiplier=multiplier,
    )
