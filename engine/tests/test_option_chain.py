import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.market.option_chain import OptionChain, OptionStrike


class OptionChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
        self.expiry = date(2026, 8, 27)

        # Strikes around 24000: 23800, 23850, 23900, 23950, 24000, 24050, 24100, 24150, 24200
        strikes = [
            OptionStrike(strike_price=23800.0, call_oi=10000, put_oi=50000),
            OptionStrike(strike_price=23850.0, call_oi=12000, put_oi=45000),
            OptionStrike(strike_price=23900.0, call_oi=15000, put_oi=40000),
            OptionStrike(strike_price=23950.0, call_oi=20000, put_oi=35000),
            OptionStrike(strike_price=24000.0, call_oi=50000, put_oi=50000),
            OptionStrike(strike_price=24050.0, call_oi=35000, put_oi=20000),
            OptionStrike(strike_price=24100.0, call_oi=40000, put_oi=15000),
            OptionStrike(strike_price=24150.0, call_oi=45000, put_oi=12000),
            OptionStrike(strike_price=24200.0, call_oi=50000, put_oi=10000),
        ]
        self.chain = OptionChain.create(
            underlying_symbol="NIFTY",
            underlying_ltp=24010.0,
            expiry_date=self.expiry,
            timestamp=self.now,
            strikes=strikes,
        )

    def test_atm_strike(self) -> None:
        # Spot is 24010 -> closest is 24000
        self.assertEqual(self.chain.get_atm_strike(), 24000.0)

    def test_total_pcr(self) -> None:
        # Total call OI: 10000+12000+15000+20000+50000+35000+40000+45000+50000 = 277000
        # Total put OI:  50000+45000+40000+35000+50000+20000+15000+12000+10000 = 277000
        self.assertEqual(self.chain.total_call_oi, 277000)
        self.assertEqual(self.chain.total_put_oi, 277000)
        self.assertAlmostEqual(self.chain.calculate_pcr("total"), 1.0)

    def test_4_itm_pcr(self) -> None:
        # Spot is 24010.0
        # ITM Calls (strike < spot): 24000, 23950, 23900, 23850
        # Call OIs: 50000 + 20000 + 15000 + 12000 = 97000
        # ITM Puts (strike > spot): 24050, 24100, 24150, 24200
        # Put OIs: 20000 + 15000 + 12000 + 10000 = 57000
        # PCR = 57000 / 97000
        expected_pcr = 57000.0 / 97000.0
        self.assertAlmostEqual(self.chain.calculate_pcr("itm_4"), expected_pcr)

    def test_zero_oi_edge_cases(self) -> None:
        empty_chain = OptionChain.create(
            underlying_symbol="NIFTY",
            underlying_ltp=24000.0,
            expiry_date=self.expiry,
            timestamp=self.now,
            strikes=[
                OptionStrike(strike_price=23900.0, call_oi=0, put_oi=0),
                OptionStrike(strike_price=24100.0, call_oi=0, put_oi=0),
            ],
        )
        self.assertEqual(empty_chain.calculate_pcr("total"), 1.0)
        self.assertEqual(empty_chain.calculate_pcr("itm_4"), 1.0)


if __name__ == "__main__":
    unittest.main()
