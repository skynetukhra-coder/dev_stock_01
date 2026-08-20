"""Paper execution engine, simulated order matching and position ledger."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from ..broker.protocols import (
    BrokerOrderResponse,
    OrderExecutionProvider,
    OrderRequest,
    OrderSide,
    OrderStatus,
    Position,
)


@dataclass
class PaperAccount:
    """Simulated account ledger tracking cash, equity and positions."""

    account_id: str = "paper-acc-01"
    initial_cash: float = 500000.0
    cash_balance: float = 500000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    orders: dict[str, BrokerOrderResponse] = field(default_factory=dict)

    @property
    def portfolio_value(self) -> float:
        """Total current market value of all open long option positions."""
        return sum(p.quantity * p.ltp for p in self.positions.values() if p.quantity > 0)

    @property
    def total_equity(self) -> float:
        """Total account equity = cash balance + market value of open positions."""
        return round(self.cash_balance + self.portfolio_value, 2)


class PaperExecutionEngine(OrderExecutionProvider):
    """In-memory simulated broker executing realistic paper trades against market quotes."""

    def __init__(self, account: Optional[PaperAccount] = None) -> None:
        self.account = account or PaperAccount()

    def place_order(
        self,
        request: OrderRequest,
        quote_price: Optional[float] = None,
    ) -> BrokerOrderResponse:
        """Execute a simulated buy or sell order against current quote price."""
        fill_price = request.price if request.price is not None else (quote_price or 100.0)
        order_id = f"paper-ord-{uuid.uuid4().hex[:8]}"

        if request.side == OrderSide.BUY:
            required_funds = fill_price * request.quantity
            if self.account.cash_balance < required_funds:
                resp = BrokerOrderResponse(
                    order_id=order_id,
                    groww_symbol=request.groww_symbol,
                    status=OrderStatus.REJECTED,
                    filled_quantity=0,
                    average_price=0.0,
                    message=(
                        f"Insufficient funds: required ₹{required_funds:.2f}, "
                        f"available ₹{self.account.cash_balance:.2f}"
                    ),
                )
                self.account.orders[order_id] = resp
                return resp

            # Debit cash balance
            self.account.cash_balance -= required_funds

            # Update or create open position
            sym = request.groww_symbol
            if sym in self.account.positions:
                curr_pos = self.account.positions[sym]
                new_qty = curr_pos.quantity + request.quantity
                new_avg = (
                    (curr_pos.quantity * curr_pos.average_price) + (request.quantity * fill_price)
                ) / new_qty
                unrealized = (fill_price - new_avg) * new_qty
                self.account.positions[sym] = Position(
                    groww_symbol=sym,
                    quantity=new_qty,
                    average_price=round(new_avg, 2),
                    ltp=fill_price,
                    pnl=round(unrealized, 2),
                    realized_pnl=curr_pos.realized_pnl,
                    unrealized_pnl=round(unrealized, 2),
                )
            else:
                self.account.positions[sym] = Position(
                    groww_symbol=sym,
                    quantity=request.quantity,
                    average_price=round(fill_price, 2),
                    ltp=fill_price,
                    pnl=0.0,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                )

        elif request.side == OrderSide.SELL:
            sym = request.groww_symbol
            curr_pos = self.account.positions.get(sym)

            if curr_pos is not None and curr_pos.quantity > 0:
                sell_qty = min(request.quantity, curr_pos.quantity)
                sale_proceeds = fill_price * sell_qty
                realized_trade = (fill_price - curr_pos.average_price) * sell_qty

                # Credit cash and update realized P&L
                self.account.cash_balance += sale_proceeds
                self.account.realized_pnl += realized_trade

                remaining_qty = curr_pos.quantity - sell_qty
                if remaining_qty == 0:
                    del self.account.positions[sym]
                else:
                    unrealized = (fill_price - curr_pos.average_price) * remaining_qty
                    self.account.positions[sym] = Position(
                        groww_symbol=sym,
                        quantity=remaining_qty,
                        average_price=curr_pos.average_price,
                        ltp=fill_price,
                        pnl=round(unrealized, 2),
                        realized_pnl=round(curr_pos.realized_pnl + realized_trade, 2),
                        unrealized_pnl=round(unrealized, 2),
                    )
            else:
                # Sell without prior position (short or flat exit)
                sale_proceeds = fill_price * request.quantity
                self.account.cash_balance += sale_proceeds

        resp = BrokerOrderResponse(
            order_id=order_id,
            groww_symbol=request.groww_symbol,
            status=OrderStatus.FILLED,
            filled_quantity=request.quantity,
            average_price=round(fill_price, 2),
            message="Paper order filled successfully",
        )
        self.account.orders[order_id] = resp
        self._recalculate_unrealized()
        return resp

    def update_quote(self, groww_symbol: str, ltp: float) -> None:
        """Mark position to market with latest price tick."""
        if groww_symbol in self.account.positions:
            pos = self.account.positions[groww_symbol]
            unrealized = (ltp - pos.average_price) * pos.quantity
            self.account.positions[groww_symbol] = Position(
                groww_symbol=groww_symbol,
                quantity=pos.quantity,
                average_price=pos.average_price,
                ltp=ltp,
                pnl=round(unrealized, 2),
                realized_pnl=pos.realized_pnl,
                unrealized_pnl=round(unrealized, 2),
            )
            self._recalculate_unrealized()

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.account.orders:
            curr = self.account.orders[order_id]
            if curr.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED):
                self.account.orders[order_id] = BrokerOrderResponse(
                    order_id=order_id,
                    groww_symbol=curr.groww_symbol,
                    status=OrderStatus.CANCELLED,
                    message="Paper order cancelled",
                )
                return True
        return False

    def get_order_status(self, order_id: str) -> OrderStatus:
        if order_id in self.account.orders:
            return self.account.orders[order_id].status
        return OrderStatus.REJECTED

    def get_positions(self) -> list[Position]:
        return list(self.account.positions.values())

    def get_account_summary(self) -> dict[str, float]:
        """Return high-level account status."""
        self._recalculate_unrealized()
        return {
            "initial_cash": self.account.initial_cash,
            "cash_balance": round(self.account.cash_balance, 2),
            "portfolio_value": round(self.account.portfolio_value, 2),
            "total_equity": self.account.total_equity,
            "realized_pnl": round(self.account.realized_pnl, 2),
            "unrealized_pnl": round(self.account.unrealized_pnl, 2),
            "total_pnl": round(self.account.realized_pnl + self.account.unrealized_pnl, 2),
        }

    def _recalculate_unrealized(self) -> None:
        tot_unrealized = sum(p.unrealized_pnl for p in self.account.positions.values())
        self.account.unrealized_pnl = round(tot_unrealized, 2)
