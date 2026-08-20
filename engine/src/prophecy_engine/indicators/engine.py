"""Unified Technical Analysis Indicator Engine and Snapshot Aggregator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from ..market.candles import CandleSeries, Timeframe
from .adx import calculate_adx
from .bollinger import calculate_bollinger_bands
from .chande_kroll import calculate_chande_kroll
from .common import atr, ema
from .moving_averages import calculate_ema_slope_and_angle
from .psar import calculate_psar
from .rsi import calculate_rsi
from .volume import calculate_volume_metrics


@dataclass(frozen=True)
class IndicatorSnapshot:
    """Immutable multi-indicator calculation snapshot for a specific symbol & timeframe."""

    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    close: float
    rsi: float
    adx: float
    plus_di: float
    minus_di: float
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    bollinger_bandwidth: float
    bollinger_percent_b: float
    psar: float
    psar_trend: int
    chande_kroll_long: float
    chande_kroll_short: float
    ema_fast: float
    ema_slow: float
    ema_slope: float
    ema_angle: float
    rvol: float
    vwap: float
    atr: float

    def is_valid(self) -> bool:
        """Check whether critical indicators have finite numeric values."""
        critical_fields = [
            self.close,
            self.rsi,
            self.adx,
            self.plus_di,
            self.minus_di,
            self.bollinger_middle,
            self.psar,
        ]
        return all(math.isfinite(val) for val in critical_fields)


class IndicatorEngine:
    """Computes full suite of technical indicators across CandleSeries."""

    def __init__(
        self,
        rsi_period: int = 14,
        adx_period: int = 14,
        bollinger_period: int = 20,
        bollinger_multiplier: float = 2.0,
        psar_af_start: float = 0.02,
        psar_af_step: float = 0.02,
        psar_af_max: float = 0.2,
        chande_p: int = 10,
        chande_x: float = 1.5,
        chande_q: int = 9,
        ema_fast_period: int = 9,
        ema_slow_period: int = 21,
    ) -> None:
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.bollinger_period = bollinger_period
        self.bollinger_multiplier = bollinger_multiplier
        self.psar_af_start = psar_af_start
        self.psar_af_step = psar_af_step
        self.psar_af_max = psar_af_max
        self.chande_p = chande_p
        self.chande_x = chande_x
        self.chande_q = chande_q
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period

    def compute_snapshot(self, series: CandleSeries) -> IndicatorSnapshot:
        """Compute all indicators for the series and package latest metrics into a snapshot."""
        if not series.candles:
            raise ValueError(f"Cannot compute indicators for empty series on {series.symbol}")

        latest_candle = series.latest
        assert latest_candle is not None

        highs = series.highs
        lows = series.lows
        closes = series.closes
        volumes = series.volumes

        # Individual calculations
        rsi_res = calculate_rsi(closes, period=self.rsi_period)
        adx_res = calculate_adx(highs, lows, closes, period=self.adx_period)
        bb_res = calculate_bollinger_bands(
            closes, period=self.bollinger_period, multiplier=self.bollinger_multiplier
        )
        psar_res = calculate_psar(
            highs,
            lows,
            closes,
            af_start=self.psar_af_start,
            af_step=self.psar_af_step,
            af_max=self.psar_af_max,
        )
        ck_res = calculate_chande_kroll(
            highs,
            lows,
            closes,
            period_p=self.chande_p,
            multiplier_x=self.chande_x,
            period_q=self.chande_q,
        )
        ema_fast_vals = ema(closes, self.ema_fast_period)
        ema_slope_res = calculate_ema_slope_and_angle(closes, period=self.ema_slow_period)
        vol_res = calculate_volume_metrics(highs, lows, closes, volumes)
        atr_vals = atr(highs, lows, closes, period=14)

        # Extract latest values safely
        latest_ema_fast = float("nan")
        for v in reversed(ema_fast_vals):
            if math.isfinite(v):
                latest_ema_fast = v
                break

        latest_atr = float("nan")
        for v in reversed(atr_vals):
            if math.isfinite(v):
                latest_atr = v
                break

        return IndicatorSnapshot(
            symbol=series.symbol,
            timeframe=series.timeframe,
            timestamp=latest_candle.timestamp,
            close=latest_candle.close,
            rsi=rsi_res.latest,
            adx=adx_res.latest_adx,
            plus_di=adx_res.latest_plus_di,
            minus_di=adx_res.latest_minus_di,
            bollinger_upper=bb_res.latest_upper,
            bollinger_middle=bb_res.latest_middle,
            bollinger_lower=bb_res.latest_lower,
            bollinger_bandwidth=bb_res.latest_bandwidth,
            bollinger_percent_b=bb_res.latest_percent_b,
            psar=psar_res.latest_sar,
            psar_trend=psar_res.latest_trend,
            chande_kroll_long=ck_res.latest_long_stop,
            chande_kroll_short=ck_res.latest_short_stop,
            ema_fast=latest_ema_fast,
            ema_slow=ema_slope_res.latest_ema,
            ema_slope=ema_slope_res.latest_slope,
            ema_angle=ema_slope_res.latest_angle,
            rvol=vol_res.latest_rvol,
            vwap=vol_res.latest_vwap,
            atr=latest_atr,
        )
