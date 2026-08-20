"""Candle data structures and timeframe series validation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Sequence


class Timeframe(str, Enum):
    """Supported strategy and market data timeframes."""

    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    D1 = "1d"

    @property
    def minutes(self) -> int:
        if self == Timeframe.M1:
            return 1
        elif self == Timeframe.M3:
            return 3
        elif self == Timeframe.M5:
            return 5
        elif self == Timeframe.M15:
            return 15
        elif self == Timeframe.M30:
            return 30
        elif self == Timeframe.D1:
            return 375  # Standard trading day minutes (09:15 to 15:30)
        raise ValueError(f"Unknown timeframe: {self}")

    @classmethod
    def from_string(cls, value: str) -> Timeframe:
        normalized = value.strip().lower()
        for tf in cls:
            if tf.value == normalized:
                return tf
        raise ValueError(f"Unsupported timeframe: {value}")


@dataclass(frozen=True)
class Candle:
    """Immutable single OHLCV bar."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: Optional[int] = None

    def __post_init__(self) -> None:
        if not (self.high >= self.low):
            raise ValueError(f"Invalid candle high ({self.high}) < low ({self.low})")
        if not (self.high >= self.open and self.high >= self.close):
            raise ValueError(f"High {self.high} must be >= open {self.open} and close {self.close}")
        if not (self.low <= self.open and self.low <= self.close):
            raise ValueError(f"Low {self.low} must be <= open {self.open} and close {self.close}")
        if self.volume < 0:
            raise ValueError(f"Volume cannot be negative: {self.volume}")
        if self.open_interest is not None and self.open_interest < 0:
            raise ValueError(f"Open interest cannot be negative: {self.open_interest}")
        for field, val in [
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
        ]:
            if not math.isfinite(val):
                raise ValueError(f"Candle {field} price must be finite, got: {val}")


@dataclass(frozen=True)
class CandleSeries:
    """Ordered sequence of candles for a specific timeframe and symbol."""

    symbol: str
    timeframe: Timeframe
    candles: tuple[Candle, ...]

    @classmethod
    def create(cls, symbol: str, timeframe: Timeframe, candles: Sequence[Candle]) -> CandleSeries:
        sorted_candles = tuple(sorted(candles, key=lambda c: c.timestamp))
        series = cls(symbol=symbol, timeframe=timeframe, candles=sorted_candles)
        series.validate()
        return series

    def validate(self) -> None:
        """Ensure candles are non-empty and strictly increasing in time."""
        if not self.candles:
            return
        for i in range(1, len(self.candles)):
            prev = self.candles[i - 1]
            curr = self.candles[i]
            if curr.timestamp <= prev.timestamp:
                raise ValueError(
                    f"Candles must be strictly ascending: {prev.timestamp} >= {curr.timestamp}"
                )

    def __len__(self) -> int:
        return len(self.candles)

    def __getitem__(self, idx: int) -> Candle:
        return self.candles[idx]

    @property
    def opens(self) -> list[float]:
        return [c.open for c in self.candles]

    @property
    def highs(self) -> list[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> list[float]:
        return [c.low for c in self.candles]

    @property
    def closes(self) -> list[float]:
        return [c.close for c in self.candles]

    @property
    def volumes(self) -> list[int]:
        return [c.volume for c in self.candles]

    @property
    def open_interests(self) -> list[Optional[int]]:
        return [c.open_interest for c in self.candles]

    @property
    def timestamps(self) -> list[datetime]:
        return [c.timestamp for c in self.candles]

    @property
    def latest(self) -> Optional[Candle]:
        return self.candles[-1] if self.candles else None

    def slice_lookback(self, count: int) -> CandleSeries:
        """Return the most recent `count` candles as a new CandleSeries."""
        if count <= 0:
            return CandleSeries(self.symbol, self.timeframe, ())
        return CandleSeries(self.symbol, self.timeframe, self.candles[-count:])
