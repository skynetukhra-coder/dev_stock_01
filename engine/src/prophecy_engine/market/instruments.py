"""Instrument definitions, option symbology and master cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Iterable, Optional, Sequence


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"
    BFO = "BFO"


class Segment(str, Enum):
    CASH = "CASH"
    FNO = "FNO"


class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"

    @classmethod
    def from_string(cls, val: str) -> OptionType:
        normalized = val.strip().upper()
        if normalized in ("CE", "CALL"):
            return cls.CE
        if normalized in ("PE", "PUT"):
            return cls.PE
        raise ValueError(f"Unknown option type: {val}")


@dataclass(frozen=True)
class Instrument:
    """Canonical instrument contract representation."""

    groww_symbol: str
    trading_symbol: str
    name: str  # Underlying or asset name, e.g. "NIFTY", "RELIANCE"
    exchange: Exchange
    segment: Segment
    lot_size: int = 1
    tick_size: float = 0.05
    expiry: Optional[date] = None
    strike_price: Optional[float] = None
    option_type: Optional[OptionType] = None
    freeze_limit: Optional[int] = None
    is_active: bool = True

    @property
    def is_option(self) -> bool:
        return (
            self.segment == Segment.FNO
            and self.option_type is not None
            and self.strike_price is not None
        )

    @property
    def is_future(self) -> bool:
        return self.segment == Segment.FNO and self.expiry is not None and self.option_type is None


class InstrumentMaster:
    """In-memory instrument registry and lookup cache."""

    def __init__(self, instruments: Optional[Sequence[Instrument]] = None) -> None:
        self._by_groww_symbol: dict[str, Instrument] = {}
        self._by_trading_symbol: dict[str, Instrument] = {}
        self._by_underlying: dict[str, list[Instrument]] = {}
        if instruments:
            self.load(instruments)

    def load(self, instruments: Iterable[Instrument]) -> None:
        """Populate or update instrument cache."""
        for inst in instruments:
            self._by_groww_symbol[inst.groww_symbol] = inst
            self._by_trading_symbol[inst.trading_symbol] = inst
            underlying = inst.name.upper()
            if underlying not in self._by_underlying:
                self._by_underlying[underlying] = []
            self._by_underlying[underlying].append(inst)

    def get_by_groww_symbol(self, groww_symbol: str) -> Optional[Instrument]:
        return self._by_groww_symbol.get(groww_symbol)

    def get_by_trading_symbol(self, trading_symbol: str) -> Optional[Instrument]:
        return self._by_trading_symbol.get(trading_symbol)

    def get_expiries(self, underlying: str) -> list[date]:
        """Return all distinct upcoming expiry dates for an underlying in ascending order."""
        instruments = self._by_underlying.get(underlying.upper(), [])
        expiries = {inst.expiry for inst in instruments if inst.expiry is not None}
        return sorted(expiries)

    def get_nearest_expiry(
        self, underlying: str, reference_date: Optional[date] = None
    ) -> Optional[date]:
        """Return the closest expiry date on or after the reference date."""
        ref = reference_date or date.today()
        expiries = [exp for exp in self.get_expiries(underlying) if exp >= ref]
        return expiries[0] if expiries else None

    def filter_options(
        self,
        underlying: str,
        expiry: Optional[date] = None,
        option_type: Optional[OptionType] = None,
        min_strike: Optional[float] = None,
        max_strike: Optional[float] = None,
    ) -> list[Instrument]:
        """Query option instruments matching specified constraints."""
        instruments = self._by_underlying.get(underlying.upper(), [])
        matches: list[Instrument] = []
        for inst in instruments:
            if not inst.is_option:
                continue
            if expiry is not None and inst.expiry != expiry:
                continue
            if option_type is not None and inst.option_type != option_type:
                continue
            if (
                min_strike is not None
                and inst.strike_price is not None
                and inst.strike_price < min_strike
            ):
                continue
            if (
                max_strike is not None
                and inst.strike_price is not None
                and inst.strike_price > max_strike
            ):
                continue
            matches.append(inst)
        return sorted(matches, key=lambda x: (x.expiry or date.min, x.strike_price or 0.0))

    def find_option(
        self,
        underlying: str,
        expiry: date,
        option_type: OptionType,
        strike_price: float,
    ) -> Optional[Instrument]:
        """Find exact matching option contract."""
        for inst in self.filter_options(underlying, expiry=expiry, option_type=option_type):
            if inst.strike_price is not None and abs(inst.strike_price - strike_price) < 1e-4:
                return inst
        return None

    def __len__(self) -> int:
        return len(self._by_groww_symbol)
