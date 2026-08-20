"""Mock and in-memory broker adapter for offline testing, backtesting and verification."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from ..market.candles import Candle, Timeframe
from ..market.instruments import Exchange, Instrument, InstrumentMaster, Segment
from ..market.option_chain import OptionChain, OptionStrike
from ..market.sessions import IST, to_ist
from .protocols import (
    BrokerOrderResponse,
    MarketDataProvider,
    OrderExecutionProvider,
    OrderRequest,
    OrderStatus,
    Position,
    Quote,
)


class MockGrowwAdapter(MarketDataProvider, OrderExecutionProvider):
    """Deterministic in-memory mock implementing MarketDataProvider and OrderExecutionProvider."""

    def __init__(self, instrument_master: Optional[InstrumentMaster] = None) -> None:
        self.instrument_master = instrument_master or InstrumentMaster()
        self.candles_db: dict[tuple[str, Timeframe], list[Candle]] = {}
        self.quotes_db: dict[str, Quote] = {}
        self.option_chains_db: dict[tuple[str, date], OptionChain] = {}
        self.orders: dict[str, BrokerOrderResponse] = {}
        self.positions: dict[str, Position] = {}

    # -------------------------------------------------------------------------
    # Fixture / Setup Helpers
    # -------------------------------------------------------------------------

    def set_candles(self, groww_symbol: str, timeframe: Timeframe, candles: list[Candle]) -> None:
        self.candles_db[(groww_symbol, timeframe)] = list(candles)

    def set_quote(self, quote: Quote) -> None:
        self.quotes_db[quote.groww_symbol] = quote

    def set_option_chain(self, option_chain: OptionChain) -> None:
        self.option_chains_db[(option_chain.underlying_symbol, option_chain.expiry_date)] = (
            option_chain
        )

    # -------------------------------------------------------------------------
    # MarketDataProvider
    # -------------------------------------------------------------------------

    def get_historical_candles(
        self,
        exchange: Exchange,
        segment: Segment,
        groww_symbol: str,
        start_time: datetime,
        end_time: datetime,
        timeframe: Timeframe,
    ) -> list[Candle]:
        start_ist = to_ist(start_time)
        end_ist = to_ist(end_time)
        stored = self.candles_db.get((groww_symbol, timeframe), [])
        return [c for c in stored if start_ist <= to_ist(c.timestamp) <= end_ist]

    def get_quote(
        self,
        exchange: Exchange,
        segment: Segment,
        groww_symbol: str,
    ) -> Quote:
        if groww_symbol in self.quotes_db:
            return self.quotes_db[groww_symbol]
        # Return fallback default quote
        return Quote(
            groww_symbol=groww_symbol,
            ltp=100.0,
            open=99.0,
            high=101.0,
            low=98.5,
            close=100.0,
            volume=10000,
            timestamp=datetime.now(IST),
        )

    def get_option_chain(
        self,
        exchange: Exchange,
        segment: Segment,
        underlying: str,
        expiry: date,
    ) -> OptionChain:
        key = (underlying.upper(), expiry)
        if key in self.option_chains_db:
            return self.option_chains_db[key]

        # Generate default synthetic 5-strike chain around 24000
        spot = 24000.0
        strikes = []
        for strike in [23800.0, 23900.0, 24000.0, 24100.0, 24200.0]:
            strikes.append(
                OptionStrike(
                    strike_price=strike,
                    call_ltp=max(1.0, spot - strike + 50.0),
                    call_oi=50000,
                    call_volume=10000,
                    put_ltp=max(1.0, strike - spot + 50.0),
                    put_oi=60000,
                    put_volume=12000,
                )
            )

        return OptionChain.create(
            underlying_symbol=underlying,
            underlying_ltp=spot,
            expiry_date=expiry,
            timestamp=datetime.now(IST),
            strikes=strikes,
        )

    def get_instruments(self) -> list[Instrument]:
        return list(self.instrument_master._by_groww_symbol.values())

    # -------------------------------------------------------------------------
    # OrderExecutionProvider
    # -------------------------------------------------------------------------

    def place_order(self, request: OrderRequest) -> BrokerOrderResponse:
        order_id = f"mock-ord-{uuid.uuid4().hex[:8]}"
        quote = self.get_quote(Exchange.NSE, Segment.CASH, request.groww_symbol)
        fill_price = request.price if request.price is not None else quote.ltp

        resp = BrokerOrderResponse(
            order_id=order_id,
            groww_symbol=request.groww_symbol,
            status=OrderStatus.FILLED,
            filled_quantity=request.quantity,
            average_price=fill_price,
            message="Mock order filled immediately",
        )
        self.orders[order_id] = resp

        # Update position
        curr_pos = self.positions.get(
            request.groww_symbol,
            Position(
                groww_symbol=request.groww_symbol,
                quantity=0,
                average_price=0.0,
                ltp=fill_price,
                pnl=0.0,
            ),
        )
        new_qty = curr_pos.quantity + request.quantity
        self.positions[request.groww_symbol] = Position(
            groww_symbol=request.groww_symbol,
            quantity=new_qty,
            average_price=fill_price,
            ltp=fill_price,
            pnl=0.0,
        )
        return resp

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            curr = self.orders[order_id]
            self.orders[order_id] = BrokerOrderResponse(
                order_id=order_id,
                groww_symbol=curr.groww_symbol,
                status=OrderStatus.CANCELLED,
                message="Order cancelled",
            )
            return True
        return False

    def get_order_status(self, order_id: str) -> OrderStatus:
        if order_id in self.orders:
            return self.orders[order_id].status
        return OrderStatus.REJECTED

    def get_positions(self) -> list[Position]:
        return list(self.positions.values())
