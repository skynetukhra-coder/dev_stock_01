import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from prophecy_engine.domain.enums import SignalStatus, SignalType
from prophecy_engine.domain.models import Signal
from prophecy_engine.market.instruments import (
    Exchange,
    Instrument,
    InstrumentMaster,
    OptionType,
    Segment,
)
from prophecy_engine.market.option_chain import OptionChain, OptionStrike
from prophecy_engine.strategy.option_selector import (
    OptionSelectionPolicy,
    OptionSelector,
    SelectionStatus,
    StrikePolicy,
)


class OptionSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)
        self.expiry = date(2026, 8, 27)

        # Strikes: 23800, 23900, 24000, 24100, 24200 (Spot = 24010 -> ATM = 24000)
        self.strikes = [
            OptionStrike(
                strike_price=23800.0,
                call_ltp=250.0,
                call_oi=10000,
                call_volume=500,
                call_bid=249.0,
                call_ask=251.0,
                put_ltp=40.0,
                put_oi=12000,
                put_volume=600,
                put_bid=39.5,
                put_ask=40.5,
            ),
            OptionStrike(
                strike_price=23900.0,
                call_ltp=170.0,
                call_oi=15000,
                call_volume=800,
                call_bid=169.0,
                call_ask=171.0,
                put_ltp=60.0,
                put_oi=18000,
                put_volume=900,
                put_bid=59.5,
                put_ask=60.5,
            ),
            OptionStrike(
                strike_price=24000.0,
                call_ltp=110.0,
                call_oi=50000,
                call_volume=2000,
                call_bid=109.5,
                call_ask=110.5,
                put_ltp=105.0,
                put_oi=55000,
                put_volume=2200,
                put_bid=104.5,
                put_ask=105.5,
            ),
            OptionStrike(
                strike_price=24100.0,
                call_ltp=65.0,
                call_oi=18000,
                call_volume=900,
                call_bid=64.5,
                call_ask=65.5,
                put_ltp=160.0,
                put_oi=14000,
                put_volume=700,
                put_bid=159.0,
                put_ask=161.0,
            ),
            OptionStrike(
                strike_price=24200.0,
                call_ltp=35.0,
                call_oi=12000,
                call_volume=600,
                call_bid=34.5,
                call_ask=35.5,
                put_ltp=240.0,
                put_oi=10000,
                put_volume=500,
                put_bid=239.0,
                put_ask=241.0,
            ),
        ]

        self.chain = OptionChain.create(
            underlying_symbol="NIFTY",
            underlying_ltp=24010.0,
            expiry_date=self.expiry,
            timestamp=self.now,
            strikes=self.strikes,
        )

        # Instrument master with ATM contracts
        self.inst_ce_24000 = Instrument(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-CE",
            trading_symbol="NIFTY26AUG24000CE",
            name="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            lot_size=25,
            tick_size=0.05,
            expiry=self.expiry,
            strike_price=24000.0,
            option_type=OptionType.CE,
        )
        self.inst_pe_24000 = Instrument(
            groww_symbol="NSE-NIFTY-2026-08-27-24000-PE",
            trading_symbol="NIFTY26AUG24000PE",
            name="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            lot_size=25,
            tick_size=0.05,
            expiry=self.expiry,
            strike_price=24000.0,
            option_type=OptionType.PE,
        )
        self.master = InstrumentMaster([self.inst_ce_24000, self.inst_pe_24000])
        self.selector = OptionSelector()

    def _make_signal(self, signal_type: SignalType) -> Signal:
        return Signal(
            id="sig-test-1",
            symbol="NIFTY",
            case_number=3,
            created_at=self.now,
            status=SignalStatus.CREATED,
            signal_type=signal_type,
            underlying_price=24010.0,
            pcr=0.75,
        )

    def test_directional_call_atm(self) -> None:
        signal = self._make_signal(SignalType.CALL)
        policy = OptionSelectionPolicy(strike_policy=StrikePolicy.ATM)

        res = self.selector.select(signal, self.chain, self.master, policy)
        self.assertTrue(res.is_success)
        self.assertIsNotNone(res.contract)
        assert res.contract is not None
        self.assertEqual(res.contract.strike, 24000.0)
        self.assertEqual(res.contract.option_type, OptionType.CE)
        self.assertEqual(res.contract.ltp, 110.0)
        self.assertEqual(res.contract.lot_size, 25)
        self.assertEqual(res.contract.quantity, 25)
        self.assertEqual(res.contract.groww_symbol, "NSE-NIFTY-2026-08-27-24000-CE")

    def test_directional_call_itm_and_otm(self) -> None:
        signal = self._make_signal(SignalType.CALL)

        # ITM_1 for Call: strike below ATM (23900)
        res_itm = self.selector.select(
            signal, self.chain, self.master, OptionSelectionPolicy(strike_policy=StrikePolicy.ITM_1)
        )
        self.assertTrue(res_itm.is_success)
        assert res_itm.contract is not None
        self.assertEqual(res_itm.contract.strike, 23900.0)
        self.assertEqual(res_itm.contract.ltp, 170.0)

        # OTM_1 for Call: strike above ATM (24100)
        res_otm = self.selector.select(
            signal, self.chain, self.master, OptionSelectionPolicy(strike_policy=StrikePolicy.OTM_1)
        )
        self.assertTrue(res_otm.is_success)
        assert res_otm.contract is not None
        self.assertEqual(res_otm.contract.strike, 24100.0)
        self.assertEqual(res_otm.contract.ltp, 65.0)

    def test_directional_put_itm_and_otm(self) -> None:
        signal = self._make_signal(SignalType.PUT)

        # ATM for Put: 24000
        res_atm = self.selector.select(
            signal, self.chain, self.master, OptionSelectionPolicy(strike_policy=StrikePolicy.ATM)
        )
        self.assertTrue(res_atm.is_success)
        assert res_atm.contract is not None
        self.assertEqual(res_atm.contract.strike, 24000.0)
        self.assertEqual(res_atm.contract.option_type, OptionType.PE)
        self.assertEqual(res_atm.contract.ltp, 105.0)

        # ITM_1 for Put: strike above ATM (24100)
        res_itm = self.selector.select(
            signal, self.chain, self.master, OptionSelectionPolicy(strike_policy=StrikePolicy.ITM_1)
        )
        self.assertTrue(res_itm.is_success)
        assert res_itm.contract is not None
        self.assertEqual(res_itm.contract.strike, 24100.0)
        self.assertEqual(res_itm.contract.ltp, 160.0)

    def test_straddle_selection(self) -> None:
        signal = self._make_signal(SignalType.STRADDLE)
        res = self.selector.select(signal, self.chain, self.master)

        self.assertTrue(res.is_success)
        self.assertIsNotNone(res.straddle)
        assert res.straddle is not None
        self.assertEqual(res.straddle.strike, 24000.0)
        self.assertEqual(res.straddle.call_contract.option_type, OptionType.CE)
        self.assertEqual(res.straddle.put_contract.option_type, OptionType.PE)
        self.assertEqual(res.straddle.combined_premium, 110.0 + 105.0)
        self.assertEqual(len(res.contracts), 2)

    def test_liquidity_filters(self) -> None:
        signal = self._make_signal(SignalType.CALL)

        # Strict OI filter rejecting 50000 OI
        strict_oi_policy = OptionSelectionPolicy(min_open_interest=100000)
        res_oi = self.selector.select(signal, self.chain, self.master, strict_oi_policy)
        self.assertEqual(res_oi.status, SelectionStatus.INSUFFICIENT_LIQUIDITY)

        # Strict Volume filter rejecting 2000 volume
        strict_vol_policy = OptionSelectionPolicy(min_volume=5000)
        res_vol = self.selector.select(signal, self.chain, self.master, strict_vol_policy)
        self.assertEqual(res_vol.status, SelectionStatus.INSUFFICIENT_LIQUIDITY)

    def test_spread_filter(self) -> None:
        signal = self._make_signal(SignalType.CALL)
        # Max spread 0.1% (bid=109.5, ask=110.5 -> spread=1.0 / 110 = 0.9%)
        tight_spread_policy = OptionSelectionPolicy(max_spread_pct=0.001)
        res = self.selector.select(signal, self.chain, self.master, tight_spread_policy)
        self.assertEqual(res.status, SelectionStatus.SPREAD_TOO_WIDE)

    def test_max_premium_ceiling(self) -> None:
        signal = self._make_signal(SignalType.CALL)
        # Max premium 100.0 (LTP is 110.0)
        cap_policy = OptionSelectionPolicy(max_premium=100.0)
        res = self.selector.select(signal, self.chain, self.master, cap_policy)
        self.assertEqual(res.status, SelectionStatus.MAX_PREMIUM_EXCEEDED)

    def test_expiry_day_policy(self) -> None:
        signal = self._make_signal(SignalType.CALL)
        # Reference date is same as expiry date (0-DTE)
        same_day = self.expiry

        # Allowed
        allow_policy = OptionSelectionPolicy(allow_expiry_day=True)
        res_allow = self.selector.select(
            signal, self.chain, self.master, allow_policy, reference_date=same_day
        )
        self.assertTrue(res_allow.is_success)

        # Disallowed
        block_policy = OptionSelectionPolicy(allow_expiry_day=False)
        res_block = self.selector.select(
            signal, self.chain, self.master, block_policy, reference_date=same_day
        )
        self.assertEqual(res_block.status, SelectionStatus.EXPIRY_TODAY_DISALLOWED)


if __name__ == "__main__":
    unittest.main()
