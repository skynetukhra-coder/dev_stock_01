import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.market.sessions import (
    IST,
    MarketSession,
    get_market_session,
    is_market_open,
    to_ist,
)


class SessionTests(unittest.TestCase):
    def test_regular_market_hours(self) -> None:
        # Tuesday at 10:30 AM IST
        dt = datetime(2026, 8, 18, 10, 30, tzinfo=IST)
        self.assertEqual(get_market_session(dt), MarketSession.REGULAR)
        self.assertTrue(is_market_open(dt))

    def test_pre_open_session(self) -> None:
        # Tuesday at 09:05 AM IST
        dt = datetime(2026, 8, 18, 9, 5, tzinfo=IST)
        self.assertEqual(get_market_session(dt), MarketSession.PRE_OPEN)
        self.assertFalse(is_market_open(dt))

    def test_post_close_session(self) -> None:
        # Tuesday at 03:45 PM IST
        dt = datetime(2026, 8, 18, 15, 45, tzinfo=IST)
        self.assertEqual(get_market_session(dt), MarketSession.POST_CLOSE)
        self.assertFalse(is_market_open(dt))

    def test_closed_at_night(self) -> None:
        # Tuesday at 08:00 PM IST
        dt = datetime(2026, 8, 18, 20, 0, tzinfo=IST)
        self.assertEqual(get_market_session(dt), MarketSession.CLOSED)
        self.assertFalse(is_market_open(dt))

    def test_closed_on_weekend(self) -> None:
        # Saturday at 11:00 AM IST
        dt = datetime(2026, 8, 22, 11, 0, tzinfo=IST)
        self.assertEqual(get_market_session(dt), MarketSession.CLOSED)
        self.assertFalse(is_market_open(dt))

    def test_timezone_normalization(self) -> None:
        # UTC 04:00 is IST 09:30 AM (during market)
        from datetime import timezone

        dt_utc = datetime(2026, 8, 18, 4, 0, tzinfo=timezone.utc)
        dt_ist = to_ist(dt_utc)
        self.assertEqual(dt_ist.hour, 9)
        self.assertEqual(dt_ist.minute, 30)
        self.assertEqual(get_market_session(dt_utc), MarketSession.REGULAR)


if __name__ == "__main__":
    unittest.main()
