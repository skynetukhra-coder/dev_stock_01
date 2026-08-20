import sys
import unittest
from datetime import date, datetime
from pathlib import Path

# Add backend and engine paths
sys.path.insert(0, str(Path(__file__).parents[2]))
sys.path.insert(0, str(Path(__file__).parents[3] / "engine" / "src"))

from fastapi.testclient import TestClient
from prophecy_engine.domain.enums import SignalStatus, SignalType
from prophecy_engine.domain.models import Signal
from prophecy_engine.market.instruments import Exchange, OptionType, Segment
from prophecy_engine.market.sessions import IST
from prophecy_engine.strategy.option_selector import SelectedContract

from app.main import app
from app.services.engine_service import engine_service


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.now = datetime(2026, 8, 20, 10, 0, tzinfo=IST)

    def test_get_health(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "prophecy-backend")
        self.assertIn("mode", data)
        self.assertIn("is_market_open", data)

    def test_signals_and_confirmation_workflow(self) -> None:
        # Step 1: Inject a synthetic signal into the engine service
        sig = Signal(
            id="sig-api-1",
            symbol="NIFTY",
            case_number=3,
            created_at=self.now,
            status=SignalStatus.CREATED,
            signal_type=SignalType.CALL,
            underlying_price=24000.0,
            pcr=0.75,
            reason="Bullish Momentum Case 3",
        )
        contract = SelectedContract(
            underlying="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            expiry=date(2026, 8, 27),
            strike=24000.0,
            option_type=OptionType.CE,
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            trading_symbol="NIFTY26AUG24000CE",
            lot_size=25,
            tick_size=0.05,
            ltp=100.0,
            bid=99.5,
            ask=100.5,
            open_interest=50000,
            volume=2000,
            quantity=25,
            num_lots=1,
            selection_reason="Test CE",
        )
        engine_service.inject_signal(sig, [contract])

        # Step 2: Query /signals
        list_resp = self.client.get("/signals")
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.json()
        self.assertGreaterEqual(list_data["total"], 1)

        # Step 3: Query /signals/sig-api-1
        get_resp = self.client.get("/signals/sig-api-1")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["id"], "sig-api-1")

        # Step 4: Confirm signal via POST /signals/sig-api-1/confirm
        conf_resp = self.client.post("/signals/sig-api-1/confirm", json={"operator_id": "op-test"})
        self.assertEqual(conf_resp.status_code, 200)
        self.assertEqual(conf_resp.json()["status"], "ROUTED")
        self.assertEqual(conf_resp.json()["orders_count"], 1)

        # Step 5: Verify order in /orders
        orders_resp = self.client.get("/orders")
        self.assertEqual(orders_resp.status_code, 200)
        self.assertGreaterEqual(orders_resp.json()["total"], 1)

        # Step 6: Verify position in /positions
        pos_resp = self.client.get("/positions")
        self.assertEqual(pos_resp.status_code, 200)
        self.assertGreaterEqual(len(pos_resp.json()), 1)

    def test_ignore_signal_workflow(self) -> None:
        sig = Signal(
            id="sig-api-ignore",
            symbol="NIFTY",
            case_number=4,
            created_at=self.now,
            status=SignalStatus.CREATED,
            signal_type=SignalType.PUT,
        )
        engine_service.inject_signal(sig, [])

        ign_resp = self.client.post(
            "/signals/sig-api-ignore/ignore",
            json={"operator_id": "op-test", "reason": "Market too volatile"},
        )
        self.assertEqual(ign_resp.status_code, 200)
        self.assertEqual(ign_resp.json()["status"], "IGNORED")

    def test_kill_switch_toggle_and_risk_status(self) -> None:
        # Activate kill switch
        resp_on = self.client.post(
            "/kill-switch", json={"active": True, "reason": "Test emergency"}
        )
        self.assertEqual(resp_on.status_code, 200)
        self.assertTrue(resp_on.json()["active"])

        # Check risk status
        risk_resp = self.client.get("/risk/status")
        self.assertEqual(risk_resp.status_code, 200)
        self.assertTrue(risk_resp.json()["kill_switch_active"])

        # Deactivate kill switch
        resp_off = self.client.post("/kill-switch", json={"active": False})
        self.assertEqual(resp_off.status_code, 200)
        self.assertFalse(resp_off.json()["active"])

    def test_account_summary(self) -> None:
        resp = self.client.get("/account/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("cash_balance", data)
        self.assertIn("total_equity", data)

    def test_backtest_endpoint(self) -> None:
        payload = {
            "symbol": "NIFTY",
            "initial_capital": 100000.0,
            "stop_loss_pct": 0.20,
            "take_profit_pct": 0.40,
            "slippage_pct": 0.001,
        }
        resp = self.client.post("/backtest", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["symbol"], "NIFTY")
        self.assertIn("win_rate", data)
        self.assertIn("profit_factor", data)
        self.assertIn("report_markdown", data)


if __name__ == "__main__":
    unittest.main()
