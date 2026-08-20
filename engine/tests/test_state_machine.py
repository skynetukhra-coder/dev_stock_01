import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.domain.enums import SignalStatus, TradeStatus
from prophecy_engine.domain.state_machine import can_trade_transition, can_transition


class StateMachineTests(unittest.TestCase):
    def test_signal_state_transitions(self) -> None:
        # Valid forward transitions
        self.assertTrue(can_transition(SignalStatus.CREATED, SignalStatus.CONFIRMED))
        self.assertTrue(can_transition(SignalStatus.CREATED, SignalStatus.IGNORED))
        self.assertTrue(can_transition(SignalStatus.CREATED, SignalStatus.EXPIRED))

        # Idempotent transitions
        self.assertTrue(can_transition(SignalStatus.CONFIRMED, SignalStatus.CONFIRMED))
        self.assertTrue(can_transition(SignalStatus.IGNORED, SignalStatus.IGNORED))

        # Invalid backward transitions
        self.assertFalse(can_transition(SignalStatus.CONFIRMED, SignalStatus.CREATED))
        self.assertFalse(can_transition(SignalStatus.IGNORED, SignalStatus.CONFIRMED))

    def test_trade_lifecycle_transitions(self) -> None:
        # Happy path: CREATED -> CONFIRMED -> ENTRY_PENDING -> ENTERED -> EXIT_PENDING -> EXITED
        self.assertTrue(can_trade_transition(TradeStatus.CREATED, TradeStatus.CONFIRMED))
        self.assertTrue(can_trade_transition(TradeStatus.CONFIRMED, TradeStatus.ENTRY_PENDING))
        self.assertTrue(can_trade_transition(TradeStatus.ENTRY_PENDING, TradeStatus.ENTERED))
        self.assertTrue(can_trade_transition(TradeStatus.ENTERED, TradeStatus.EXIT_PENDING))
        self.assertTrue(can_trade_transition(TradeStatus.EXIT_PENDING, TradeStatus.EXITED))

        # Partial fill branch
        self.assertTrue(
            can_trade_transition(TradeStatus.ENTRY_PENDING, TradeStatus.PARTIALLY_FILLED)
        )
        self.assertTrue(can_trade_transition(TradeStatus.PARTIALLY_FILLED, TradeStatus.ENTERED))
        self.assertTrue(
            can_trade_transition(TradeStatus.PARTIALLY_FILLED, TradeStatus.EXIT_PENDING)
        )

        # Reject branch
        self.assertTrue(can_trade_transition(TradeStatus.ENTRY_PENDING, TradeStatus.REJECTED))

        # Error branch from any in-flight state
        self.assertTrue(can_trade_transition(TradeStatus.ENTRY_PENDING, TradeStatus.ERROR))
        self.assertTrue(can_trade_transition(TradeStatus.ENTERED, TradeStatus.ERROR))

        # Idempotent
        self.assertTrue(can_trade_transition(TradeStatus.EXITED, TradeStatus.EXITED))
        self.assertTrue(can_trade_transition(TradeStatus.REJECTED, TradeStatus.REJECTED))

        # Invalid transition
        self.assertFalse(can_trade_transition(TradeStatus.EXITED, TradeStatus.ENTERED))


if __name__ == "__main__":
    unittest.main()
