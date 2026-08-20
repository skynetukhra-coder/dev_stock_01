"""Average Directional Index (ADX) and Directional Movement Index (+DI, -DI)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ADXResult:
    """ADX, +DI, and -DI indicator calculation series."""

    adx: tuple[float, ...]
    plus_di: tuple[float, ...]
    minus_di: tuple[float, ...]
    dx: tuple[float, ...]
    period: int

    @property
    def latest_adx(self) -> float:
        for val in reversed(self.adx):
            if math.isfinite(val):
                return val
        return float("nan")

    @property
    def latest_plus_di(self) -> float:
        for val in reversed(self.plus_di):
            if math.isfinite(val):
                return val
        return float("nan")

    @property
    def latest_minus_di(self) -> float:
        for val in reversed(self.minus_di):
            if math.isfinite(val):
                return val
        return float("nan")


def calculate_adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> ADXResult:
    """Calculate Average Directional Index (ADX) using Wilder's DMI formulation.

    Requires at least (2 * period) candles for a fully stabilized ADX value.
    """
    if period <= 0:
        raise ValueError(f"ADX period must be positive, got {period}")

    n = len(highs)
    if not (n == len(lows) == len(closes)):
        raise ValueError("High, low and close sequences must have matching lengths")

    adx_series = [float("nan")] * n
    plus_di_series = [float("nan")] * n
    minus_di_series = [float("nan")] * n
    dx_series = [float("nan")] * n

    if n <= period:
        return ADXResult(
            adx=tuple(adx_series),
            plus_di=tuple(plus_di_series),
            minus_di=tuple(minus_di_series),
            dx=tuple(dx_series),
            period=period,
        )

    # Calculate True Range, +DM, -DM
    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n

    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        h = highs[i]
        low_val = lows[i]
        prev_h = highs[i - 1]
        prev_l = lows[i - 1]
        prev_c = closes[i - 1]

        # TR
        tr[i] = max(h - low_val, abs(h - prev_c), abs(low_val - prev_c))

        # +DM / -DM
        up_move = h - prev_h
        down_move = prev_l - low_val

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Wilder initial smoothing sums for period
    smoothed_tr = sum(tr[1 : period + 1])
    smoothed_plus_dm = sum(plus_dm[1 : period + 1])
    smoothed_minus_dm = sum(minus_dm[1 : period + 1])

    # First DI and DX at index `period`
    if smoothed_tr > 0:
        p_di = 100.0 * (smoothed_plus_dm / smoothed_tr)
        m_di = 100.0 * (smoothed_minus_dm / smoothed_tr)
    else:
        p_di, m_di = 0.0, 0.0

    plus_di_series[period] = p_di
    minus_di_series[period] = m_di
    di_sum = p_di + m_di
    dx_series[period] = 100.0 * (abs(p_di - m_di) / di_sum) if di_sum > 0 else 0.0

    # Iterative calculation for subsequent DIs and DX
    for i in range(period + 1, n):
        smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr[i]
        smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm[i]
        smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm[i]

        if smoothed_tr > 0:
            p_di = 100.0 * (smoothed_plus_dm / smoothed_tr)
            m_di = 100.0 * (smoothed_minus_dm / smoothed_tr)
        else:
            p_di, m_di = 0.0, 0.0

        plus_di_series[i] = p_di
        minus_di_series[i] = m_di
        di_sum = p_di + m_di
        dx_series[i] = 100.0 * (abs(p_di - m_di) / di_sum) if di_sum > 0 else 0.0

    # Compute ADX from DX series
    # First ADX is the average of DX over `period` from index `period` to `2 * period - 1`
    start_adx_idx = 2 * period - 1
    if n > start_adx_idx:
        valid_dxs = [dx_series[j] for j in range(period, start_adx_idx + 1)]
        current_adx = sum(valid_dxs) / period
        adx_series[start_adx_idx] = current_adx

        for i in range(start_adx_idx + 1, n):
            current_adx = (current_adx * (period - 1) + dx_series[i]) / period
            adx_series[i] = current_adx

    return ADXResult(
        adx=tuple(adx_series),
        plus_di=tuple(plus_di_series),
        minus_di=tuple(minus_di_series),
        dx=tuple(dx_series),
        period=period,
    )
