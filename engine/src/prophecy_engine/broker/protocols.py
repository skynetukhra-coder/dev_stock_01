"""Broker and market data protocol contracts, request/response models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from ..market.candles import Candle, Timeframe
from ..market.instruments import Exchange, Instrument, Segment
from ..market.option_chain import OptionChain


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Quote:
    """Real-time market quote snapshot."""

    groww_symbol: str
    ltp: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    open_interest: Optional[int] = None
    bid: float = 0.0
    ask: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass(frozen=True)
class OrderRequest:
    """Broker-neutral order placement specification."""

    groww_symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    price: Optional[float] = None
    idempotency_key: Optional[str] = None
    tag: Optional[str] = None


@dataclass(frozen=True)
class BrokerOrderResponse:
    """Immediate response returned by broker on order placement or inquiry."""

    order_id: str
    groww_symbol: str
    status: OrderStatus
    filled_quantity: int = 0
    average_price: float = 0.0
    message: Optional[str] = None


@dataclass(frozen=True)
class Position:
    """Current broker position record."""

    groww_symbol: str
    quantity: int
    average_price: float
    ltp: float
    pnl: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0


@runtime_checkable
class MarketDataProvider(Protocol):
    """Protocol for fetching market candles, quotes, option chains and instruments."""

    def get_historical_candles(
        self,
        exchange: Exchange,
        segment: Segment,
        groww_symbol: str,
        start_time: datetime,
        end_time: datetime,
        timeframe: Timeframe,
    ) -> list[Candle]:
        """Fetch historical OHLCV candles."""
        ...

    def get_quote(
        self,
        exchange: Exchange,
        segment: Segment,
        groww_symbol: str,
    ) -> Quote:
        """Fetch real-time snapshot quote."""
        ...

    def get_option_chain(
        self,
        exchange: Exchange,
        segment: Segment,
        underlying: str,
        expiry: date,
    ) -> OptionChain:
        """Fetch option chain snapshot for underlying and expiry."""
        ...

    def get_instruments(self) -> list[Instrument]:
        """Fetch instrument master records."""
        ...


@runtime_checkable
class OrderExecutionProvider(Protocol):
    """Protocol for order placement, cancellation and position queries."""

    def place_order(self, request: OrderRequest) -> BrokerOrderResponse:
        """Submit an order to the broker (feature-gated)."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order with the broker."""
        ...

    def get_order_status(self, order_id: str) -> OrderStatus:
        """Query the status of an existing broker order."""
        ...

    def get_positions(self) -> list[Position]:
        """Fetch current active positions from the broker."""
        ...
