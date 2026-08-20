import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.config import EngineConfig, TradingMode
from prophecy_engine.domain.enums import SignalStatus
from prophecy_engine.domain.state_machine import can_transition


class BootstrapTests(unittest.TestCase):
    def test_default_mode_is_signal(self) -> None:
        self.assertEqual(EngineConfig().trading_mode, TradingMode.SIGNAL)

    def test_confirmation_transition_is_allowed(self) -> None:
        self.assertTrue(can_transition(SignalStatus.CREATED, SignalStatus.CONFIRMED))


if __name__ == "__main__":
    unittest.main()
