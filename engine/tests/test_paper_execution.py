import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.broker.protocols import OrderRequest, OrderSide, OrderStatus
from prophecy_engine.execution.paper import PaperAccount, PaperExecutionEngine


class PaperExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.account = PaperAccount(initial_cash=100000.0, cash_balance=100000.0)
        self.engine = PaperExecutionEngine(self.account)

    def test_buy_order_placement_and_cash_debit(self) -> None:
        # Buy 50 Qty @ 100.0 = ₹5,000
        req = OrderRequest(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            side=OrderSide.BUY,
            quantity=50,
            price=100.0,
        )
        resp = self.engine.place_order(req)

        self.assertEqual(resp.status, OrderStatus.FILLED)
        self.assertEqual(resp.filled_quantity, 50)
        self.assertEqual(self.account.cash_balance, 95000.0)
        self.assertEqual(len(self.account.positions), 1)

        pos = self.account.positions["NSE-NIFTY-2026-08-27-24000-CE"]
        self.assertEqual(pos.quantity, 50)
        self.assertEqual(pos.average_price, 100.0)

    def test_insufficient_funds_rejection(self) -> None:
        # Try to buy ₹200,000 with ₹100,000 cash
        req = OrderRequest(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            side=OrderSide.BUY,
            quantity=2000,
            price=100.0,
        )
        resp = self.engine.place_order(req)
        self.assertEqual(resp.status, OrderStatus.REJECTED)
        self.assertIn("Insufficient funds", resp.message or "")
        self.assertEqual(self.account.cash_balance, 100000.0)

    def test_multiple_buys_weighted_average(self) -> None:
        sym = "NSE-NIFTY-2026-08-27-24000-CE"
        # First buy: 25 @ 100 = 2500
        self.engine.place_order(OrderRequest(sym, OrderSide.BUY, 25, price=100.0))
        # Second buy: 25 @ 120 = 3000
        self.engine.place_order(OrderRequest(sym, OrderSide.BUY, 25, price=120.0))

        pos = self.account.positions[sym]
        self.assertEqual(pos.quantity, 50)
        self.assertEqual(pos.average_price, 110.0)  # (2500 + 3000) / 50 = 110.0
        self.assertEqual(self.account.cash_balance, 100000.0 - 5500.0)

    def test_sell_order_realized_pnl(self) -> None:
        sym = "NSE-NIFTY-2026-08-27-24000-CE"
        # Buy: 50 @ 100 = ₹5,000 (cash = 95,000)
        self.engine.place_order(OrderRequest(sym, OrderSide.BUY, 50, price=100.0))

        # Partial Sell: 25 @ 130 = ₹3,250 (gain = 25 * 30 = ₹750)
        self.engine.place_order(OrderRequest(sym, OrderSide.SELL, 25, price=130.0))

        self.assertEqual(self.account.cash_balance, 95000.0 + 3250.0)
        self.assertEqual(self.account.realized_pnl, 750.0)
        self.assertEqual(self.account.positions[sym].quantity, 25)

        # Full Exit: remaining 25 @ 90 = ₹2,250 (loss = 25 * -10 = -₹250)
        self.engine.place_order(OrderRequest(sym, OrderSide.SELL, 25, price=90.0))

        self.assertEqual(self.account.cash_balance, 98250.0 + 2250.0)
        self.assertEqual(self.account.realized_pnl, 500.0)  # 750 - 250 = 500
        self.assertNotIn(sym, self.account.positions)

    def test_mark_to_market_quote_updates(self) -> None:
        sym = "NSE-NIFTY-2026-08-27-24000-CE"
        self.engine.place_order(OrderRequest(sym, OrderSide.BUY, 50, price=100.0))

        # Update quote price to 115.0 (+15 per unit * 50 = +750)
        self.engine.update_quote(sym, 115.0)

        summary = self.engine.get_account_summary()
        self.assertEqual(summary["unrealized_pnl"], 750.0)
        self.assertEqual(summary["portfolio_value"], 5750.0)
        self.assertEqual(summary["total_equity"], 95000.0 + 5750.0)


if __name__ == "__main__":
    unittest.main()
