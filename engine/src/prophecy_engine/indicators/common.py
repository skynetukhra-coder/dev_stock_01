"""Common mathematical utilities, smoothing algorithms, and moving averages."""

from __future__ import annotations

import math
from typing import Sequence


def sma(values: Sequence[float], period: int) -> list[float]:
    """Calculate Simple Moving Average over a sliding window.

    Returns a list of length equal to len(values). Elements before index `period - 1` are NaN.
    """
    if period <= 0:
        raise ValueError(f"Period must be positive, got {period}")
    n = len(values)
    result = [float("nan")] * n
    if n < period:
        return result

    running_sum = sum(values[:period])
    result[period - 1] = running_sum / period

    for i in range(period, n):
        running_sum += values[i] - values[i - period]
        result[i] = running_sum / period

    return result


def ema(values: Sequence[float], period: int) -> list[float]:
    """Calculate Exponential Moving Average.

    Uses standard smoothing multiplier alpha = 2 / (period + 1).
    Seed value at index `period - 1` is the SMA of the initial `period` elements.
    """
    if period <= 0:
        raise ValueError(f"Period must be positive, got {period}")
    n = len(values)
    result = [float("nan")] * n
    if n < period:
        return result

    alpha = 2.0 / (period + 1.0)
    initial_sma = sum(values[:period]) / period
    result[period - 1] = initial_sma

    current_ema = initial_sma
    for i in range(period, n):
        current_ema = alpha * values[i] + (1.0 - alpha) * current_ema
        result[i] = current_ema

    return result


def wilder_smooth(values: Sequence[float], period: int) -> list[float]:
    """Calculate Wilder's smoothed moving average (modified moving average / RMA).

    Equivalent to EMA with alpha = 1 / period.
    Initial seed at index `period - 1` is the sum (or average depending on metric).
    Here the series returns the smoothed average values.
    """
    if period <= 0:
        raise ValueError(f"Period must be positive, got {period}")
    n = len(values)
    result = [float("nan")] * n
    if n < period:
        return result

    # Initial seed is simple average of first `period` items
    current_val = sum(values[:period]) / period
    result[period - 1] = current_val

    for i in range(period, n):
        current_val = (current_val * (period - 1) + values[i]) / period
        result[i] = current_val

    return result


def standard_deviation(values: Sequence[float], period: int, ddof: int = 0) -> list[float]:
    """Calculate rolling standard deviation over sliding window."""
    if period <= 0:
        raise ValueError(f"Period must be positive, got {period}")
    n = len(values)
    result = [float("nan")] * n
    if n < period:
        return result

    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / max(1, period - ddof)
        result[i] = math.sqrt(variance)

    return result


def true_range(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]
) -> list[float]:
    """Calculate True Range (TR) series for given High, Low, Close bars."""
    n = len(highs)
    if not (n == len(lows) == len(closes)):
        raise ValueError("High, low and close sequences must have matching lengths")
    if n == 0:
        return []

    tr = [0.0] * n
    tr[0] = highs[0] - lows[0]

    for i in range(1, n):
        h = highs[i]
        low_val = lows[i]
        prev_c = closes[i - 1]
        tr[i] = max(h - low_val, abs(h - prev_c), abs(low_val - prev_c))

    return tr


def atr(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14
) -> list[float]:
    """Calculate Average True Range (ATR) using Wilder's smoothing."""
    tr = true_range(highs, lows, closes)
    return wilder_smooth(tr, period)
