"""Relative Strength Index (RSI) using Wilder's smoothing."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class RSIResult:
    """RSI calculation output containing full series and latest value."""

    values: tuple[float, ...]
    period: int

    @property
    def latest(self) -> float:
        """Return the most recent non-NaN RSI value, or NaN if insufficient data."""
        for val in reversed(self.values):
            if math.isfinite(val):
                return val
        return float("nan")


def calculate_rsi(closes: Sequence[float], period: int = 14) -> RSIResult:
    """Calculate Relative Strength Index (RSI) across a series of close prices.

    Uses Wilder's smoothing algorithm.
    Range: [0.0, 100.0].
    """
    if period <= 0:
        raise ValueError(f"RSI period must be positive, got {period}")

    n = len(closes)
    result = [float("nan")] * n
    if n <= period:
        return RSIResult(values=tuple(result), period=period)

    # Compute price changes
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains[i] = diff
        else:
            losses[i] = -diff

    # Initial seed average
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period

    if avg_loss == 0.0:
        result[period] = 100.0 if avg_gain > 0.0 else 50.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    # Wilder smoothing iteration
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0.0:
            result[i] = 100.0 if avg_gain > 0.0 else 50.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return RSIResult(values=tuple(result), period=period)
