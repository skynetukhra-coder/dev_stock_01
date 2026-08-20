"""Groww broker and market data adapter using modern GrowwAPI interfaces."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional, Union

from ..config import EngineConfig, TradingMode
from ..market.candles import Candle, Timeframe
from ..market.instruments import Exchange, Instrument, OptionType, Segment
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


class GrowwAdapterError(Exception):
    """Base exception for Groww broker adapter errors."""

    pass


class GrowwAuthenticationError(GrowwAdapterError):
    """Raised when authentication with Groww fails."""

    pass


class GrowwAdapter(MarketDataProvider, OrderExecutionProvider):
    """Adapter for Groww Trade API.

    Adheres to MarketDataProvider and OrderExecutionProvider protocols.
    Order execution is strictly gated by the configured trading_mode.
    """

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        groww_client: Optional[Any] = None,
    ) -> None:
        self._config = config or EngineConfig.from_environment()
        self._client = groww_client

    @property
    def client(self) -> Any:
        """Lazily initialize GrowwAPI client if not injected."""
        if self._client is None:
            if not self._config.groww.is_configured:
                raise GrowwAuthenticationError(
                    "Groww credentials are not configured. Set GROWW_API_KEY or GROWW_ACCESS_TOKEN."
                )
            try:
                # Import modern Groww SDK
                from growwapi import GrowwAPI  # type: ignore

                if self._config.groww.access_token:
                    self._client = GrowwAPI(access_token=self._config.groww.access_token)
                else:
                    self._client = GrowwAPI(
                        api_key=self._config.groww.api_key,
                        api_secret=self._config.groww.api_secret,
                    )
            except ImportError:
                raise GrowwAdapterError(
                    "growwapi package is not installed. Install via `pip install growwapi`."
                )
            except Exception as e:
                raise GrowwAuthenticationError(f"Failed to initialize GrowwAPI client: {e}") from e
        return self._client

    # -------------------------------------------------------------------------
    # MarketDataProvider Implementation
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
        """Fetch historical candles via Groww get_historical_candles API."""
        start_ist = to_ist(start_time)
        end_ist = to_ist(end_time)

        raw_response = self.client.get_historical_candles(
            exchange=exchange.value,
            segment=segment.value,
            groww_symbol=groww_symbol,
            start_time=start_ist.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end_ist.strftime("%Y-%m-%d %H:%M:%S"),
            interval_in_minutes=timeframe.minutes,
        )

        return self._parse_candles_response(raw_response)

    def get_quote(
        self,
        exchange: Exchange,
        segment: Segment,
        groww_symbol: str,
    ) -> Quote:
        """Fetch current quote / LTP snapshot."""
        raw = self.client.get_quote(
            exchange=exchange.value,
            segment=segment.value,
            groww_symbol=groww_symbol,
        )
        return self._parse_quote_response(groww_symbol, raw)

    def get_option_chain(
        self,
        exchange: Exchange,
        segment: Segment,
        underlying: str,
        expiry: date,
    ) -> OptionChain:
        """Fetch option chain for underlying and expiry date."""
        raw = self.client.get_option_chain(
            exchange=exchange.value,
            segment=segment.value,
            underlying=underlying,
            expiry=expiry.isoformat(),
        )
        return self._parse_option_chain_response(underlying, expiry, raw)

    def get_instruments(self) -> list[Instrument]:
        """Load instrument list from Groww."""
        raw = self.client.get_instruments()
        return self._parse_instruments_response(raw)

    # -------------------------------------------------------------------------
    # OrderExecutionProvider Implementation (Safety Gated)
    # -------------------------------------------------------------------------

    def place_order(self, request: OrderRequest) -> BrokerOrderResponse:
        """Place order with Groww broker."""
        self._assert_live_execution_allowed()
        raw = self.client.place_order(
            groww_symbol=request.groww_symbol,
            order_type=request.order_type.value,
            transaction_type=request.side.value,
            quantity=request.quantity,
            price=request.price,
            tag=request.tag,
        )
        return BrokerOrderResponse(
            order_id=str(raw.get("order_id") or raw.get("orderId")),
            groww_symbol=request.groww_symbol,
            status=OrderStatus.SUBMITTED,
            message="Order submitted to broker",
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing open order with Groww broker."""
        self._assert_live_execution_allowed()
        res = self.client.cancel_order(order_id=order_id)
        return bool(res.get("status") in ("CANCELLED", "SUCCESS", True))

    def get_order_status(self, order_id: str) -> OrderStatus:
        """Query order status from Groww."""
        raw = self.client.get_order_status(order_id=order_id)
        status_str = str(raw.get("status", "")).upper()
        if "FILL" in status_str:
            return OrderStatus.FILLED
        elif "PARTIAL" in status_str:
            return OrderStatus.PARTIALLY_FILLED
        elif "CANCEL" in status_str:
            return OrderStatus.CANCELLED
        elif "REJECT" in status_str:
            return OrderStatus.REJECTED
        return OrderStatus.SUBMITTED

    def get_positions(self) -> list[Position]:
        """Query open and closed positions from Groww."""
        raw = self.client.get_positions()
        items = raw if isinstance(raw, list) else raw.get("positions", [])
        positions: list[Position] = []
        for item in items:
            positions.append(
                Position(
                    groww_symbol=item["groww_symbol"],
                    quantity=int(item.get("quantity", 0)),
                    average_price=float(item.get("average_price", item.get("avg_price", 0.0))),
                    ltp=float(item.get("ltp", 0.0)),
                    pnl=float(item.get("pnl", 0.0)),
                    realized_pnl=float(item.get("realized_pnl", 0.0)),
                    unrealized_pnl=float(item.get("unrealized_pnl", 0.0)),
                )
            )
        return positions

    # -------------------------------------------------------------------------
    # Internal Helpers and Parsers
    # -------------------------------------------------------------------------

    def _assert_live_execution_allowed(self) -> None:
        if self._config.trading_mode is not TradingMode.LIVE:
            msg = (
                f"Live broker order execution is prohibited when "
                f"trading_mode={self._config.trading_mode.value}. "
                "Set TRADING_MODE=LIVE only after passing acceptance criteria."
            )
            raise RuntimeError(msg)

    @staticmethod
    def _parse_timestamp(ts: Union[int, float, str, datetime]) -> datetime:
        if isinstance(ts, datetime):
            return to_ist(ts)
        if isinstance(ts, (int, float)):
            # Epoch milliseconds vs seconds check
            if ts > 1e11:
                return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).astimezone(IST)
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
        if isinstance(ts, str):
            # Parse ISO or standard Groww format "YYYY-MM-DD HH:MM:SS"
            clean_ts = ts.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(clean_ts)
            except ValueError:
                dt = datetime.strptime(clean_ts, "%Y-%m-%d %H:%M:%S")
            return to_ist(dt)
        raise ValueError(f"Unparseable timestamp: {ts}")

    def _parse_candles_response(self, raw: Any) -> list[Candle]:
        candles_data = raw.get("candles") if isinstance(raw, dict) else raw
        if not candles_data:
            return []

        results: list[Candle] = []
        for item in candles_data:
            if isinstance(item, (list, tuple)):
                # [timestamp, open, high, low, close, volume, optional(oi)]
                ts = self._parse_timestamp(item[0])
                o = float(item[1])
                h = float(item[2])
                low_val = float(item[3])
                c = float(item[4])
                v = int(item[5])
                oi = int(item[6]) if len(item) > 6 and item[6] is not None else None
                results.append(Candle(ts, o, h, low_val, c, v, oi))
            elif isinstance(item, dict):
                ts = self._parse_timestamp(item.get("timestamp") or item.get("time"))
                results.append(
                    Candle(
                        timestamp=ts,
                        open=float(item["open"]),
                        high=float(item["high"]),
                        low=float(item["low"]),
                        close=float(item["close"]),
                        volume=int(item.get("volume", 0)),
                        open_interest=int(item["open_interest"])
                        if item.get("open_interest") is not None
                        else None,
                    )
                )
        return results

    def _parse_quote_response(self, groww_symbol: str, raw: dict[str, Any]) -> Quote:
        ts = self._parse_timestamp(raw["timestamp"]) if "timestamp" in raw else datetime.now(IST)
        return Quote(
            groww_symbol=groww_symbol,
            ltp=float(raw.get("ltp", raw.get("last_price", 0.0))),
            open=float(raw.get("open", 0.0)),
            high=float(raw.get("high", 0.0)),
            low=float(raw.get("low", 0.0)),
            close=float(raw.get("close", 0.0)),
            volume=int(raw.get("volume", 0)),
            open_interest=int(raw["open_interest"])
            if raw.get("open_interest") is not None
            else None,
            bid=float(raw.get("bid", raw.get("best_bid_price", 0.0))),
            ask=float(raw.get("ask", raw.get("best_ask_price", 0.0))),
            timestamp=ts,
        )

    def _parse_option_chain_response(
        self, underlying: str, expiry: date, raw: dict[str, Any]
    ) -> OptionChain:
        spot_ltp = float(raw.get("underlying_ltp", raw.get("spot_price", raw.get("ltp", 0.0))))
        ts = self._parse_timestamp(raw["timestamp"]) if "timestamp" in raw else datetime.now(IST)

        strikes_list: list[OptionStrike] = []
        raw_strikes = raw.get("strikes", raw.get("option_chain", []))
        for item in raw_strikes:
            strike_price = float(item["strike_price"])
            ce_data = item.get("call") or item.get("ce") or {}
            pe_data = item.get("put") or item.get("pe") or {}

            strike_obj = OptionStrike(
                strike_price=strike_price,
                call_ltp=float(ce_data.get("ltp", ce_data.get("last_price", 0.0))),
                call_oi=int(ce_data.get("open_interest", ce_data.get("oi", 0))),
                call_volume=int(ce_data.get("volume", 0)),
                call_iv=float(ce_data["iv"]) if ce_data.get("iv") is not None else None,
                call_bid=float(ce_data.get("bid", 0.0)),
                call_ask=float(ce_data.get("ask", 0.0)),
                put_ltp=float(pe_data.get("ltp", pe_data.get("last_price", 0.0))),
                put_oi=int(pe_data.get("open_interest", pe_data.get("oi", 0))),
                put_volume=int(pe_data.get("volume", 0)),
                put_iv=float(pe_data["iv"]) if pe_data.get("iv") is not None else None,
                put_bid=float(pe_data.get("bid", 0.0)),
                put_ask=float(pe_data.get("ask", 0.0)),
            )
            strikes_list.append(strike_obj)

        return OptionChain.create(
            underlying_symbol=underlying,
            underlying_ltp=spot_ltp,
            expiry_date=expiry,
            timestamp=ts,
            strikes=strikes_list,
        )

    def _parse_instruments_response(self, raw: Any) -> list[Instrument]:
        items = raw if isinstance(raw, list) else raw.get("instruments", [])
        instruments: list[Instrument] = []
        for item in items:
            opt_type = (
                OptionType.from_string(item["option_type"]) if item.get("option_type") else None
            )
            exp_date = (
                date.fromisoformat(item["expiry"])
                if item.get("expiry") and isinstance(item["expiry"], str)
                else item.get("expiry")
            )
            inst = Instrument(
                groww_symbol=item["groww_symbol"],
                trading_symbol=item.get("trading_symbol", item["groww_symbol"]),
                name=item.get("name", item.get("underlying", "")),
                exchange=Exchange(item.get("exchange", "NSE")),
                segment=Segment(item.get("segment", "CASH")),
                lot_size=int(item.get("lot_size", 1)),
                tick_size=float(item.get("tick_size", 0.05)),
                expiry=exp_date,
                strike_price=float(item["strike_price"])
                if item.get("strike_price") is not None
                else None,
                option_type=opt_type,
                freeze_limit=int(item["freeze_limit"])
                if item.get("freeze_limit") is not None
                else None,
                is_active=bool(item.get("is_active", True)),
            )
            instruments.append(inst)
        return instruments
