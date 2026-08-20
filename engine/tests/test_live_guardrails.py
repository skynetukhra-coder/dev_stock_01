import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.broker.mock import MockGrowwAdapter
from prophecy_engine.broker.protocols import OrderRequest, OrderSide, OrderStatus, Quote
from prophecy_engine.domain.enums import SignalStatus, SignalType
from prophecy_engine.domain.models import Signal
from prophecy_engine.execution.live_gate import (
    LiveBrokerAdapter,
    LiveSafetyConfig,
    LiveSafetyGate,
    LiveTradingDisabledError,
)
from prophecy_engine.market.sessions import IST


class LiveGuardrailsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 20, 10, 0, tzinfo=IST)
        self.config = LiveSafetyConfig(
            max_order_quantity=100,
            max_order_notional=35000.0,
            max_price_deviation_pct=0.10,
            token_ttl_seconds=60,
        )
        self.gate = LiveSafetyGate(self.config)
        self.mock_adapter = MockGrowwAdapter()
        self.live_adapter = LiveBrokerAdapter(self.mock_adapter, self.gate)

        self.signal = Signal(
            id="sig-live-1",
            symbol="NIFTY",
            case_number=3,
            created_at=self.now,
            status=SignalStatus.CONFIRMED,
            signal_type=SignalType.CALL,
            underlying_price=24000.0,
            pcr=0.75,
        )

        self.valid_env = {
            "PROPHECY_EXECUTION_MODE": "LIVE",
            "PROPHECY_LIVE_TRADING_ACKNOWLEDGED": "TRUE",
            "PROPHECY_OPERATOR_SIGNATURE": "OP-SEC-9988",
        }

        self.valid_order = OrderRequest(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            side=OrderSide.BUY,
            quantity=25,
            price=100.0,
        )
        self.valid_quote = Quote(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            ltp=100.0,
            timestamp=self.now,
        )

    def test_lock_1_env_authorization_blocks(self) -> None:
        token = self.gate.generate_confirmation_token(self.signal, "op-1", timestamp=self.now)

        # Missing ack
        bad_env = dict(self.valid_env)
        bad_env["PROPHECY_LIVE_TRADING_ACKNOWLEDGED"] = "FALSE"
        res = self.gate.verify_live_order(
            self.valid_order, self.valid_quote, token, env_vars=bad_env, current_time=self.now
        )
        self.assertFalse(res.is_valid)
        self.assertIn("LOCK_1_LIVE_TRADING_NOT_ACKNOWLEDGED", res.failed_locks)

        # Missing signature
        bad_env2 = dict(self.valid_env)
        bad_env2["PROPHECY_OPERATOR_SIGNATURE"] = ""
        res2 = self.gate.verify_live_order(
            self.valid_order, self.valid_quote, token, env_vars=bad_env2, current_time=self.now
        )
        self.assertFalse(res2.is_valid)
        self.assertIn("LOCK_1_OPERATOR_SIGNATURE_MISSING", res2.failed_locks)

    def test_lock_2_kill_switch_blocks(self) -> None:
        token = self.gate.generate_confirmation_token(self.signal, "op-1", timestamp=self.now)
        res = self.gate.verify_live_order(
            self.valid_order,
            self.valid_quote,
            token,
            is_kill_switch_active=True,
            env_vars=self.valid_env,
            current_time=self.now,
        )
        self.assertFalse(res.is_valid)
        self.assertIn("LOCK_2_KILL_SWITCH_ACTIVE", res.failed_locks)

    def test_lock_3_confirmation_token_validation(self) -> None:
        # 1. Missing token
        res_missing = self.gate.verify_live_order(
            self.valid_order,
            self.valid_quote,
            token=None,
            env_vars=self.valid_env,
            current_time=self.now,
        )
        self.assertFalse(res_missing.is_valid)
        self.assertIn("LOCK_3_CONFIRMATION_TOKEN_MISSING", res_missing.failed_locks)

        # 2. Expired token (> 60s)
        old_time = self.now - timedelta(seconds=70)
        token_expired = self.gate.generate_confirmation_token(
            self.signal, "op-1", timestamp=old_time
        )
        res_expired = self.gate.verify_live_order(
            self.valid_order,
            self.valid_quote,
            token_expired,
            env_vars=self.valid_env,
            current_time=self.now,
        )
        self.assertFalse(res_expired.is_valid)
        self.assertIn("LOCK_3_CONFIRMATION_TOKEN_EXPIRED", res_expired.failed_locks)

    def test_lock_4_quantity_ceiling_exceeded(self) -> None:
        token = self.gate.generate_confirmation_token(self.signal, "op-1", timestamp=self.now)
        huge_order = OrderRequest(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            side=OrderSide.BUY,
            quantity=200,  # Max is 100
            price=100.0,
        )
        res = self.gate.verify_live_order(
            huge_order, self.valid_quote, token, env_vars=self.valid_env, current_time=self.now
        )
        self.assertFalse(res.is_valid)
        self.assertIn("LOCK_4_QUANTITY_CEILING_EXCEEDED", res.failed_locks)

    def test_lock_5_notional_ceiling_exceeded(self) -> None:
        token = self.gate.generate_confirmation_token(self.signal, "op-1", timestamp=self.now)
        # Notional = 500 * 80 = 40,000 (Max is 35,000)
        expensive_order = OrderRequest(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            side=OrderSide.BUY,
            quantity=80,
            price=500.0,
        )
        quote = Quote(groww_symbol="NSE-NIFTY-2026-08-27-24000-CE", ltp=500.0, timestamp=self.now)
        res = self.gate.verify_live_order(
            expensive_order, quote, token, env_vars=self.valid_env, current_time=self.now
        )
        self.assertFalse(res.is_valid)
        self.assertIn("LOCK_5_NOTIONAL_CEILING_EXCEEDED", res.failed_locks)

    def test_lock_6_fat_finger_price_deviation(self) -> None:
        token = self.gate.generate_confirmation_token(self.signal, "op-1", timestamp=self.now)
        # Price is 150.0 on a 100.0 LTP quote (50% deviation > 10% limit)
        deviant_order = OrderRequest(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            side=OrderSide.BUY,
            quantity=25,
            price=150.0,
        )
        res = self.gate.verify_live_order(
            deviant_order, self.valid_quote, token, env_vars=self.valid_env, current_time=self.now
        )
        self.assertFalse(res.is_valid)
        self.assertIn("LOCK_6_FAT_FINGER_PRICE_DEVIATION", res.failed_locks)

    def test_live_adapter_success_and_single_use_token(self) -> None:
        token = self.gate.generate_confirmation_token(self.signal, "op-1", timestamp=self.now)

        # First placement succeeds
        resp = self.live_adapter.place_order(
            request=self.valid_order,
            quote=self.valid_quote,
            token=token,
            env_vars=self.valid_env,
            current_time=self.now,
        )
        self.assertEqual(resp.status, OrderStatus.FILLED)
        self.assertEqual(resp.filled_quantity, 25)

        # Second attempt with same token fails (replay attack prevention)
        with self.assertRaises(LiveTradingDisabledError):
            self.live_adapter.place_order(
                request=self.valid_order,
                quote=self.valid_quote,
                token=token,
                env_vars=self.valid_env,
                current_time=self.now,
            )


if __name__ == "__main__":
    unittest.main()
