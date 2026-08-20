"""Option chain data models, strike matrices and PCR calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Sequence

from .instruments import Instrument


@dataclass(frozen=True)
class OptionStrike:
    """Consolidated Call and Put market data for a single strike price."""

    strike_price: float
    call_instrument: Optional[Instrument] = None
    call_ltp: float = 0.0
    call_oi: int = 0
    call_volume: int = 0
    call_iv: Optional[float] = None
    call_bid: float = 0.0
    call_ask: float = 0.0
    put_instrument: Optional[Instrument] = None
    put_ltp: float = 0.0
    put_oi: int = 0
    put_volume: int = 0
    put_iv: Optional[float] = None
    put_bid: float = 0.0
    put_ask: float = 0.0


@dataclass(frozen=True)
class OptionChain:
    """Option chain snapshot for a specific underlying and expiry."""

    underlying_symbol: str
    underlying_ltp: float
    expiry_date: date
    timestamp: datetime
    strikes: tuple[OptionStrike, ...]

    @classmethod
    def create(
        cls,
        underlying_symbol: str,
        underlying_ltp: float,
        expiry_date: date,
        timestamp: datetime,
        strikes: Sequence[OptionStrike],
    ) -> OptionChain:
        sorted_strikes = tuple(sorted(strikes, key=lambda s: s.strike_price))
        return cls(
            underlying_symbol=underlying_symbol,
            underlying_ltp=underlying_ltp,
            expiry_date=expiry_date,
            timestamp=timestamp,
            strikes=sorted_strikes,
        )

    def get_atm_strike(self) -> float:
        """Find the strike price closest to the underlying spot price."""
        if not self.strikes:
            raise ValueError("Cannot find ATM strike in an empty option chain")
        return min(
            self.strikes, key=lambda s: abs(s.strike_price - self.underlying_ltp)
        ).strike_price

    def get_strike(self, strike_price: float) -> Optional[OptionStrike]:
        """Find strike data by exact price."""
        for s in self.strikes:
            if abs(s.strike_price - strike_price) < 1e-4:
                return s
        return None

    @property
    def total_call_oi(self) -> int:
        return sum(s.call_oi for s in self.strikes)

    @property
    def total_put_oi(self) -> int:
        return sum(s.put_oi for s in self.strikes)

    @property
    def total_call_volume(self) -> int:
        return sum(s.call_volume for s in self.strikes)

    @property
    def total_put_volume(self) -> int:
        return sum(s.put_volume for s in self.strikes)

    def calculate_pcr(self, mode: str = "total") -> float:
        """Calculate Put-Call Ratio (PCR) by Open Interest.

        Modes:
        - "total": Sum of all Put OI / Sum of all Call OI.
        - "itm_4": Custom strategy formula: Sum of 4 nearest ITM Puts OI /
                   Sum of 4 nearest ITM Calls OI.
                   (ITM Call: strike < spot; ITM Put: strike > spot).
        """
        if mode == "total":
            c_oi = self.total_call_oi
            p_oi = self.total_put_oi
            if c_oi == 0:
                return float("inf") if p_oi > 0 else 1.0
            return p_oi / c_oi

        elif mode == "itm_4":
            spot = self.underlying_ltp
            # ITM Calls: strikes below spot (sorted descending to get closest to spot)
            itm_calls = [s for s in self.strikes if s.strike_price < spot]
            itm_calls.sort(key=lambda s: s.strike_price, reverse=True)
            nearest_itm_calls = itm_calls[:4]

            # ITM Puts: strikes above spot (sorted ascending to get closest to spot)
            itm_puts = [s for s in self.strikes if s.strike_price > spot]
            itm_puts.sort(key=lambda s: s.strike_price)
            nearest_itm_puts = itm_puts[:4]

            call_oi_sum = sum(s.call_oi for s in nearest_itm_calls)
            put_oi_sum = sum(s.put_oi for s in nearest_itm_puts)

            if call_oi_sum == 0:
                return float("inf") if put_oi_sum > 0 else 1.0
            return put_oi_sum / call_oi_sum

        else:
            raise ValueError(f"Unknown PCR mode: {mode}. Supported modes are 'total' and 'itm_4'")
