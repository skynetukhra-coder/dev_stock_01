"""Volume indicators: Volume SMA, Relative Volume (RVOL), and VWAP."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .common import sma


@dataclass(frozen=True)
class VolumeResult:
    """Volume analytics series and metrics."""

    volume_sma: tuple[float, ...]
    rvol: tuple[float, ...]
    vwap: tuple[float, ...]
    period: int

    @property
    def latest_volume_sma(self) -> float:
        for val in reversed(self.volume_sma):
            if math.isfinite(val):
                return val
        return float("nan")

    @property
    def latest_rvol(self) -> float:
        for val in reversed(self.rvol):
            if math.isfinite(val):
                return val
        return float("nan")

    @property
    def latest_vwap(self) -> float:
        for val in reversed(self.vwap):
            if math.isfinite(val):
                return val
        return float("nan")


def calculate_volume_metrics(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[int],
    period: int = 20,
) -> VolumeResult:
    """Calculate Volume SMA, Relative Volume (RVOL), and cumulative VWAP."""
    n = len(volumes)
    if not (n == len(highs) == len(lows) == len(closes)):
        raise ValueError("Price and volume sequences must have matching lengths")

    float_vols = [float(v) for v in volumes]
    vol_sma = sma(float_vols, period)

    rvol = [float("nan")] * n
    for i in range(period - 1, n):
        avg_v = vol_sma[i]
        if math.isfinite(avg_v) and avg_v > 0:
            rvol[i] = float_vols[i] / avg_v
        else:
            rvol[i] = 1.0

    # Calculate VWAP
    vwap = [float("nan")] * n
    cum_tp_vol = 0.0
    cum_vol = 0.0

    for i in range(n):
        tp = (highs[i] + lows[i] + closes[i]) / 3.0
        v = float_vols[i]
        cum_tp_vol += tp * v
        cum_vol += v
        if cum_vol > 0:
            vwap[i] = cum_tp_vol / cum_vol
        else:
            vwap[i] = closes[i]

    return VolumeResult(
        volume_sma=tuple(vol_sma),
        rvol=tuple(rvol),
        vwap=tuple(vwap),
        period=period,
    )
