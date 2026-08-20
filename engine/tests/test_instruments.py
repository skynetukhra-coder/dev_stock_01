import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.market.instruments import (
    Exchange,
    Instrument,
    InstrumentMaster,
    OptionType,
    Segment,
)


class InstrumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inst1 = Instrument(
            groww_symbol="NSE-NIFTY-2026-08-27-24500-CE",
            trading_symbol="NIFTY26AUG24500CE",
            name="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            lot_size=25,
            tick_size=0.05,
            expiry=date(2026, 8, 27),
            strike_price=24500.0,
            option_type=OptionType.CE,
        )
        self.inst2 = Instrument(
            groww_symbol="NSE-NIFTY-2026-08-27-24500-PE",
            trading_symbol="NIFTY26AUG24500PE",
            name="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            lot_size=25,
            tick_size=0.05,
            expiry=date(2026, 8, 27),
            strike_price=24500.0,
            option_type=OptionType.PE,
        )
        self.inst3 = Instrument(
            groww_symbol="NSE-NIFTY-2026-09-03-24600-CE",
            trading_symbol="NIFTY26SEP24600CE",
            name="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            lot_size=25,
            tick_size=0.05,
            expiry=date(2026, 9, 3),
            strike_price=24600.0,
            option_type=OptionType.CE,
        )
        self.equity_inst = Instrument(
            groww_symbol="NSE-RELIANCE",
            trading_symbol="RELIANCE",
            name="RELIANCE",
            exchange=Exchange.NSE,
            segment=Segment.CASH,
            lot_size=1,
            tick_size=0.05,
        )
        self.master = InstrumentMaster([self.inst1, self.inst2, self.inst3, self.equity_inst])

    def test_instrument_properties(self) -> None:
        self.assertTrue(self.inst1.is_option)
        self.assertFalse(self.inst1.is_future)
        self.assertFalse(self.equity_inst.is_option)

    def test_master_lookups(self) -> None:
        self.assertEqual(
            self.master.get_by_groww_symbol("NSE-NIFTY-2026-08-27-24500-CE"),
            self.inst1,
        )
        self.assertEqual(
            self.master.get_by_trading_symbol("NIFTY26AUG24500PE"),
            self.inst2,
        )
        self.assertIsNone(self.master.get_by_groww_symbol("UNKNOWN"))

    def test_expiries_and_nearest(self) -> None:
        expiries = self.master.get_expiries("NIFTY")
        self.assertEqual(expiries, [date(2026, 8, 27), date(2026, 9, 3)])

        nearest = self.master.get_nearest_expiry("NIFTY", reference_date=date(2026, 8, 20))
        self.assertEqual(nearest, date(2026, 8, 27))

        after_first = self.master.get_nearest_expiry("NIFTY", reference_date=date(2026, 8, 28))
        self.assertEqual(after_first, date(2026, 9, 3))

    def test_filter_and_find_options(self) -> None:
        filtered = self.master.filter_options(
            "NIFTY",
            expiry=date(2026, 8, 27),
            option_type=OptionType.CE,
        )
        self.assertEqual(filtered, [self.inst1])

        found = self.master.find_option("NIFTY", date(2026, 8, 27), OptionType.PE, 24500.0)
        self.assertEqual(found, self.inst2)

        not_found = self.master.find_option("NIFTY", date(2026, 8, 27), OptionType.CE, 25000.0)
        self.assertIsNone(not_found)


if __name__ == "__main__":
    unittest.main()
