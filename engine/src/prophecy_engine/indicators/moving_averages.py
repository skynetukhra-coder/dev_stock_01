"""Moving averages, exponential moving averages, slope, and directional angles."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .common import ema, sma


@dataclass(frozen=True)
class EMASlopeResult:
    """EMA series with associated directional slope and angle."""

    ema: tuple[float, ...]
    slope: tuple[float, ...]
    angle_degrees: tuple[float, ...]
    period: int
    lookback: int

    @property
    def latest_ema(self) -> float:
        return self._latest(self.ema)

    @property
    def latest_slope(self) -> float:
        return self._latest(self.slope)

    @property
    def latest_angle(self) -> float:
        return self._latest(self.angle_degrees)

    @staticmethod
    def _latest(series: tuple[float, ...]) -> float:
        for val in reversed(series):
            if math.isfinite(val):
                return val
        return float("nan")


def calculate_ema(closes: Sequence[float], period: int = 20) -> list[float]:
    """Calculate standard Exponential Moving Average."""
    return ema(closes, period)


def calculate_sma(closes: Sequence[float], period: int = 20) -> list[float]:
    """Calculate standard Simple Moving Average."""
    return sma(closes, period)


def calculate_ema_slope_and_angle(
    closes: Sequence[float],
    period: int = 20,
    lookback: int = 1,
    price_scale: float = 1.0,
) -> EMASlopeResult:
    """Calculate EMA, its directional rate of change (slope) and angle in degrees.

    Preserves direction: upward trend has positive slope/angle, downward trend has negative.
    """
    if lookback <= 0:
        raise ValueError(f"Lookback must be positive, got {lookback}")

    ema_vals = ema(closes, period)
    n = len(ema_vals)

    slope = [float("nan")] * n
    angle_deg = [float("nan")] * n

    for i in range(period - 1 + lookback, n):
        curr = ema_vals[i]
        prev = ema_vals[i - lookback]
        if math.isfinite(curr) and math.isfinite(prev):
            s = (curr - prev) / float(lookback)
            slope[i] = s
            # Angle in degrees = arctan(slope / scale) * (180 / pi)
            scaled_slope = s / price_scale if price_scale != 0.0 else s
            rad = math.atan(scaled_slope)
            angle_deg[i] = math.degrees(rad)

    return EMASlopeResult(
        ema=tuple(ema_vals),
        slope=tuple(slope),
        angle_degrees=tuple(angle_deg),
        period=period,
        lookback=lookback,
    )
