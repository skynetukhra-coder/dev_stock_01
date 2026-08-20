"""Option selector: converts trading signals into concrete option contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

from ..domain.enums import SignalType
from ..domain.models import Signal
from ..market.instruments import Exchange, InstrumentMaster, OptionType, Segment
from ..market.option_chain import OptionChain, OptionStrike


class StrikePolicy(str, Enum):
    """Strike selection rule relative to spot ATM strike."""

    ATM = "ATM"
    ITM_1 = "ITM_1"
    ITM_2 = "ITM_2"
    OTM_1 = "OTM_1"
    OTM_2 = "OTM_2"


class SelectionStatus(str, Enum):
    """Status outcomes for option contract selection."""

    SUCCESS = "SUCCESS"
    NO_EXPIRY = "NO_EXPIRY"
    NO_STRIKE = "NO_STRIKE"
    INSUFFICIENT_LIQUIDITY = "INSUFFICIENT_LIQUIDITY"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    MAX_PREMIUM_EXCEEDED = "MAX_PREMIUM_EXCEEDED"
    EXPIRY_TODAY_DISALLOWED = "EXPIRY_TODAY_DISALLOWED"
    INVALID_SIGNAL = "INVALID_SIGNAL"


@dataclass(frozen=True)
class SelectedContract:
    """Resolved and validated option contract ready for order placement or simulation."""

    underlying: str
    exchange: Exchange
    segment: Segment
    expiry: date
    strike: float
    option_type: OptionType
    groww_symbol: str
    trading_symbol: str
    lot_size: int
    tick_size: float
    ltp: float
    bid: float
    ask: float
    open_interest: int
    volume: int
    quantity: int
    num_lots: int
    selection_reason: str


@dataclass(frozen=True)
class SelectedStraddle:
    """Resolved ATM Call + Put contract pair for straddle strategies."""

    underlying: str
    expiry: date
    strike: float
    call_contract: SelectedContract
    put_contract: SelectedContract
    combined_premium: float
    selection_reason: str


@dataclass(frozen=True)
class SelectionResult:
    """Output of OptionSelector resolution."""

    status: SelectionStatus
    contract: Optional[SelectedContract] = None
    straddle: Optional[SelectedStraddle] = None
    message: str = ""

    @property
    def is_success(self) -> bool:
        return self.status == SelectionStatus.SUCCESS

    @property
    def contracts(self) -> list[SelectedContract]:
        if self.straddle is not None:
            return [self.straddle.call_contract, self.straddle.put_contract]
        elif self.contract is not None:
            return [self.contract]
        return []


@dataclass(frozen=True)
class OptionSelectionPolicy:
    """Rules and risk constraints for selecting option strikes."""

    strike_policy: StrikePolicy = StrikePolicy.ATM
    min_open_interest: int = 5000
    min_volume: int = 100
    max_spread_pct: float = 0.15  # Max 15% bid-ask spread relative to LTP
    max_premium: Optional[float] = None
    allow_expiry_day: bool = True
    default_lots: int = 1


class OptionSelector:
    """Resolves Signals into concrete tradeable option contracts."""

    def __init__(self, default_policy: Optional[OptionSelectionPolicy] = None) -> None:
        self.default_policy = default_policy or OptionSelectionPolicy()

    def select(
        self,
        signal: Signal,
        option_chain: OptionChain,
        instrument_master: Optional[InstrumentMaster] = None,
        policy: Optional[OptionSelectionPolicy] = None,
        reference_date: Optional[date] = None,
    ) -> SelectionResult:
        """Select concrete contract(s) matching signal type, strike policy and liquidity rules."""
        active_policy = policy or self.default_policy
        ref_date = reference_date or signal.created_at.date()

        # Step 1: Validate Expiry Date
        expiry = option_chain.expiry_date
        if expiry < ref_date:
            return SelectionResult(
                status=SelectionStatus.NO_EXPIRY,
                message=f"Option chain expiry {expiry} is in the past relative to {ref_date}",
            )

        if not active_policy.allow_expiry_day and expiry == ref_date:
            return SelectionResult(
                status=SelectionStatus.EXPIRY_TODAY_DISALLOWED,
                message=f"Trading on expiry day {expiry} is disabled by policy",
            )

        # Step 2: Handle Straddle vs Directional
        if signal.signal_type in (SignalType.STRADDLE, SignalType.STRADDLE_SPECIAL):
            return self._select_straddle(
                signal=signal,
                chain=option_chain,
                instrument_master=instrument_master,
                policy=active_policy,
            )
        elif signal.signal_type in (
            SignalType.CALL,
            SignalType.CALL_SPECIAL,
            SignalType.PUT,
            SignalType.PUT_SPECIAL,
        ):
            return self._select_directional(
                signal=signal,
                chain=option_chain,
                instrument_master=instrument_master,
                policy=active_policy,
            )
        else:
            return SelectionResult(
                status=SelectionStatus.INVALID_SIGNAL,
                message=f"Unsupported signal type for option selection: {signal.signal_type}",
            )

    def _select_directional(
        self,
        signal: Signal,
        chain: OptionChain,
        instrument_master: Optional[InstrumentMaster],
        policy: OptionSelectionPolicy,
    ) -> SelectionResult:
        is_call = signal.signal_type in (SignalType.CALL, SignalType.CALL_SPECIAL)
        opt_type = OptionType.CE if is_call else OptionType.PE

        # Resolve target strike based on strike policy
        target_strike_data = self._resolve_target_strike(
            chain=chain,
            opt_type=opt_type,
            policy=policy.strike_policy,
        )
        if target_strike_data is None:
            return SelectionResult(
                status=SelectionStatus.NO_STRIKE,
                message=f"Could not locate matching strike for policy {policy.strike_policy.value}",
            )

        # Validate liquidity, spread, and premium
        validation_err = self._validate_liquidity_and_spread(
            strike_data=target_strike_data,
            opt_type=opt_type,
            policy=policy,
        )
        if validation_err is not None:
            return validation_err

        # Build SelectedContract
        strike_val = target_strike_data.strike_price
        reason_msg = (
            f"{signal.signal_type.value} @ {policy.strike_policy.value} (Strike {strike_val})"
        )
        contract = self._build_contract(
            underlying=chain.underlying_symbol,
            expiry=chain.expiry_date,
            strike_data=target_strike_data,
            opt_type=opt_type,
            instrument_master=instrument_master,
            policy=policy,
            reason=reason_msg,
        )

        return SelectionResult(status=SelectionStatus.SUCCESS, contract=contract)

    def _select_straddle(
        self,
        signal: Signal,
        chain: OptionChain,
        instrument_master: Optional[InstrumentMaster],
        policy: OptionSelectionPolicy,
    ) -> SelectionResult:
        # Straddles always execute at ATM strike
        try:
            atm_strike = chain.get_atm_strike()
        except ValueError:
            return SelectionResult(status=SelectionStatus.NO_STRIKE, message="Empty option chain")

        strike_data = chain.get_strike(atm_strike)
        if strike_data is None:
            return SelectionResult(
                status=SelectionStatus.NO_STRIKE,
                message=f"ATM Strike {atm_strike} not found in chain",
            )

        # Validate CE
        err_ce = self._validate_liquidity_and_spread(strike_data, OptionType.CE, policy)
        if err_ce is not None:
            return err_ce

        # Validate PE
        err_pe = self._validate_liquidity_and_spread(strike_data, OptionType.PE, policy)
        if err_pe is not None:
            return err_pe

        ce_contract = self._build_contract(
            underlying=chain.underlying_symbol,
            expiry=chain.expiry_date,
            strike_data=strike_data,
            opt_type=OptionType.CE,
            instrument_master=instrument_master,
            policy=policy,
            reason=f"Straddle Leg 1: CE @ {atm_strike}",
        )

        pe_contract = self._build_contract(
            underlying=chain.underlying_symbol,
            expiry=chain.expiry_date,
            strike_data=strike_data,
            opt_type=OptionType.PE,
            instrument_master=instrument_master,
            policy=policy,
            reason=f"Straddle Leg 2: PE @ {atm_strike}",
        )

        combined = ce_contract.ltp + pe_contract.ltp

        straddle = SelectedStraddle(
            underlying=chain.underlying_symbol,
            expiry=chain.expiry_date,
            strike=atm_strike,
            call_contract=ce_contract,
            put_contract=pe_contract,
            combined_premium=combined,
            selection_reason=f"{signal.signal_type.value} ATM Straddle (Strike {atm_strike})",
        )

        return SelectionResult(status=SelectionStatus.SUCCESS, straddle=straddle)

    def _resolve_target_strike(
        self,
        chain: OptionChain,
        opt_type: OptionType,
        policy: StrikePolicy,
    ) -> Optional[OptionStrike]:
        if not chain.strikes:
            return None

        atm_strike = chain.get_atm_strike()
        sorted_strikes = list(chain.strikes)
        atm_idx = -1
        for idx, s in enumerate(sorted_strikes):
            if abs(s.strike_price - atm_strike) < 1e-4:
                atm_idx = idx
                break

        if atm_idx == -1:
            return None

        if policy == StrikePolicy.ATM:
            return sorted_strikes[atm_idx]

        offset = 0
        if policy in (StrikePolicy.ITM_1, StrikePolicy.ITM_2):
            steps = 1 if policy == StrikePolicy.ITM_1 else 2
            # For CE, ITM is lower strike (-offset); for PE, ITM is higher strike (+offset)
            offset = -steps if opt_type == OptionType.CE else steps

        elif policy in (StrikePolicy.OTM_1, StrikePolicy.OTM_2):
            steps = 1 if policy == StrikePolicy.OTM_1 else 2
            # For CE, OTM is higher strike (+offset); for PE, OTM is lower strike (-offset)
            offset = steps if opt_type == OptionType.CE else -steps

        target_idx = atm_idx + offset
        if 0 <= target_idx < len(sorted_strikes):
            return sorted_strikes[target_idx]

        return None

    def _validate_liquidity_and_spread(
        self,
        strike_data: OptionStrike,
        opt_type: OptionType,
        policy: OptionSelectionPolicy,
    ) -> Optional[SelectionResult]:
        oi = strike_data.call_oi if opt_type == OptionType.CE else strike_data.put_oi
        vol = strike_data.call_volume if opt_type == OptionType.CE else strike_data.put_volume
        ltp = strike_data.call_ltp if opt_type == OptionType.CE else strike_data.put_ltp
        bid = strike_data.call_bid if opt_type == OptionType.CE else strike_data.put_bid
        ask = strike_data.call_ask if opt_type == OptionType.CE else strike_data.put_ask

        # 1. Open Interest filter
        if oi < policy.min_open_interest:
            msg = f"{opt_type.value} OI ({oi}) below required minimum ({policy.min_open_interest})"
            return SelectionResult(status=SelectionStatus.INSUFFICIENT_LIQUIDITY, message=msg)

        # 2. Volume filter
        if vol < policy.min_volume:
            msg = f"{opt_type.value} Volume ({vol}) below required minimum ({policy.min_volume})"
            return SelectionResult(status=SelectionStatus.INSUFFICIENT_LIQUIDITY, message=msg)

        # 3. Spread filter (if quotes are available)
        if bid > 0 and ask > 0 and ltp > 0:
            spread_pct = (ask - bid) / ltp
            if spread_pct > policy.max_spread_pct:
                msg = (
                    f"{opt_type.value} spread ({spread_pct:.1%}) exceeds "
                    f"maximum ({policy.max_spread_pct:.1%})"
                )
                return SelectionResult(status=SelectionStatus.SPREAD_TOO_WIDE, message=msg)

        # 4. Premium ceiling filter
        if policy.max_premium is not None and ltp > policy.max_premium:
            msg = f"{opt_type.value} LTP ({ltp}) exceeds max premium limit ({policy.max_premium})"
            return SelectionResult(status=SelectionStatus.MAX_PREMIUM_EXCEEDED, message=msg)

        return None

    def _build_contract(
        self,
        underlying: str,
        expiry: date,
        strike_data: OptionStrike,
        opt_type: OptionType,
        instrument_master: Optional[InstrumentMaster],
        policy: OptionSelectionPolicy,
        reason: str,
    ) -> SelectedContract:
        strike_price = strike_data.strike_price
        inst = None
        if instrument_master is not None:
            inst = instrument_master.find_option(underlying, expiry, opt_type, strike_price)

        if inst is not None:
            groww_symbol = inst.groww_symbol
            trading_symbol = inst.trading_symbol
            lot_size = inst.lot_size
            tick_size = inst.tick_size
            exchange = inst.exchange
            segment = inst.segment
        else:
            # Fallback canonical symbol formatting
            und_up = underlying.upper()
            exp_iso = expiry.isoformat()
            exp_str = expiry.strftime("%y%b").upper()
            sp_int = int(strike_price)
            groww_symbol = f"NSE-{und_up}-{exp_iso}-{sp_int}-{opt_type.value}"
            trading_symbol = f"{und_up}{exp_str}{sp_int}{opt_type.value}"
            lot_size = 25 if "NIFTY" in und_up else 1
            tick_size = 0.05
            exchange = Exchange.NSE
            segment = Segment.FNO

        ltp = strike_data.call_ltp if opt_type == OptionType.CE else strike_data.put_ltp
        bid = strike_data.call_bid if opt_type == OptionType.CE else strike_data.put_bid
        ask = strike_data.call_ask if opt_type == OptionType.CE else strike_data.put_ask
        oi = strike_data.call_oi if opt_type == OptionType.CE else strike_data.put_oi
        vol = strike_data.call_volume if opt_type == OptionType.CE else strike_data.put_volume

        num_lots = max(1, policy.default_lots)
        quantity = num_lots * lot_size

        return SelectedContract(
            underlying=underlying.upper(),
            exchange=exchange,
            segment=segment,
            expiry=expiry,
            strike=strike_price,
            option_type=opt_type,
            groww_symbol=groww_symbol,
            trading_symbol=trading_symbol,
            lot_size=lot_size,
            tick_size=tick_size,
            ltp=ltp,
            bid=bid,
            ask=ask,
            open_interest=oi,
            volume=vol,
            quantity=quantity,
            num_lots=num_lots,
            selection_reason=reason,
        )
