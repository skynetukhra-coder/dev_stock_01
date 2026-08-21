"""Simulation endpoint for generating and validating Cases 1 to 6 in real-time."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from typing import Any
from fastapi import APIRouter, HTTPException

from prophecy_engine.domain.enums import SignalStatus, SignalType
from prophecy_engine.domain.models import Signal
from prophecy_engine.indicators.engine import IndicatorSnapshot
from prophecy_engine.market.candles import Timeframe
from prophecy_engine.market.instruments import Exchange, Instrument, OptionType, Segment
from prophecy_engine.market.option_chain import OptionChain, OptionStrike
from prophecy_engine.market.sessions import IST
from prophecy_engine.strategy.cases import REQUIRED_TIMEFRAMES, evaluate_all_cases
from prophecy_engine.strategy.option_selector import OptionSelectionPolicy, OptionSelector
from ..services.engine_service import engine_service

router = APIRouter(prefix="/simulate", tags=["Strategy Simulation & Validation"])


def _create_synthetic_snapshots(case_num: int) -> tuple[dict[Timeframe, IndicatorSnapshot], float]:
    """Generate valid 5-timeframe indicator snapshots satisfying the requested case."""
    now = datetime.now(IST)
    snapshots: dict[Timeframe, IndicatorSnapshot] = {}

    if case_num == 1:
        # Case 1: Straddle (ADX 15-30, RSI 40-60 on all TFs)
        pcr = 0.95
        for tf in REQUIRED_TIMEFRAMES:
            snapshots[tf] = IndicatorSnapshot(
                symbol="NIFTY",
                timeframe=tf,
                timestamp=now,
                close=24000.0,
                rsi=50.0,
                adx=22.0,
                plus_di=20.0,
                minus_di=20.0,
                bollinger_upper=24100.0,
                bollinger_middle=24000.0,
                bollinger_lower=23900.0,
                bollinger_bandwidth=0.03,
                bollinger_percent_b=0.50,
                psar=23950.0,
                psar_trend=1,
                chande_kroll_long=23950.0,
                chande_kroll_short=24050.0,
                ema_fast=24005.0,
                ema_slow=24000.0,
                ema_slope=0.5,
                ema_angle=5.0,
                rvol=1.2,
                vwap=24000.0,
                atr=45.0,
            )
    elif case_num == 2:
        # Case 2: Straddle Special (ADX 0-10, RSI 40-60 on all TFs)
        pcr = 0.90
        for tf in REQUIRED_TIMEFRAMES:
            snapshots[tf] = IndicatorSnapshot(
                symbol="NIFTY",
                timeframe=tf,
                timestamp=now,
                close=24000.0,
                rsi=48.0,
                adx=6.5,
                plus_di=18.0,
                minus_di=18.0,
                bollinger_upper=24080.0,
                bollinger_middle=24000.0,
                bollinger_lower=23920.0,
                bollinger_bandwidth=0.02,
                bollinger_percent_b=0.50,
                psar=23960.0,
                psar_trend=1,
                chande_kroll_long=23960.0,
                chande_kroll_short=24040.0,
                ema_fast=24002.0,
                ema_slow=24000.0,
                ema_slope=0.2,
                ema_angle=2.0,
                rvol=2.2,
                vwap=24000.0,
                atr=35.0,
            )
    elif case_num == 3:
        # Case 3: Directional Call (ADX 15-30, RSI 0-60 on all TFs, PCR < 0.8)
        pcr = 0.65
        for tf in REQUIRED_TIMEFRAMES:
            snapshots[tf] = IndicatorSnapshot(
                symbol="NIFTY",
                timeframe=tf,
                timestamp=now,
                close=24000.0,
                rsi=55.0,
                adx=25.0,
                plus_di=30.0,
                minus_di=15.0,
                bollinger_upper=24150.0,
                bollinger_middle=24000.0,
                bollinger_lower=23850.0,
                bollinger_bandwidth=0.05,
                bollinger_percent_b=0.75,
                psar=23900.0,
                psar_trend=1,
                chande_kroll_long=23920.0,
                chande_kroll_short=24120.0,
                ema_fast=24020.0,
                ema_slow=23980.0,
                ema_slope=2.0,
                ema_angle=22.0,
                rvol=1.8,
                vwap=23990.0,
                atr=50.0,
            )
    elif case_num == 4:
        # Case 4: Directional Put (ADX 15-30, RSI 45-100 on all TFs, PCR > 1.25)
        pcr = 1.45
        for tf in REQUIRED_TIMEFRAMES:
            snapshots[tf] = IndicatorSnapshot(
                symbol="NIFTY",
                timeframe=tf,
                timestamp=now,
                close=24000.0,
                rsi=48.0,
                adx=26.0,
                plus_di=14.0,
                minus_di=32.0,
                bollinger_upper=24150.0,
                bollinger_middle=24000.0,
                bollinger_lower=23850.0,
                bollinger_bandwidth=0.05,
                bollinger_percent_b=0.25,
                psar=24100.0,
                psar_trend=-1,
                chande_kroll_long=23880.0,
                chande_kroll_short=24080.0,
                ema_fast=23980.0,
                ema_slow=24020.0,
                ema_slope=-2.0,
                ema_angle=-22.0,
                rvol=1.9,
                vwap=24010.0,
                atr=52.0,
            )
    elif case_num == 5:
        # Case 5: Call Special (RSI 0-25 extreme oversold on all TFs)
        pcr = 0.55
        for tf in REQUIRED_TIMEFRAMES:
            snapshots[tf] = IndicatorSnapshot(
                symbol="NIFTY",
                timeframe=tf,
                timestamp=now,
                close=24000.0,
                rsi=20.0,
                adx=35.0,
                plus_di=10.0,
                minus_di=40.0,
                bollinger_upper=24200.0,
                bollinger_middle=24000.0,
                bollinger_lower=23800.0,
                bollinger_bandwidth=0.06,
                bollinger_percent_b=0.05,
                psar=24150.0,
                psar_trend=-1,
                chande_kroll_long=23750.0,
                chande_kroll_short=24100.0,
                ema_fast=23900.0,
                ema_slow=24000.0,
                ema_slope=-3.5,
                ema_angle=-35.0,
                rvol=2.8,
                vwap=24020.0,
                atr=65.0,
            )
    elif case_num == 6:
        # Case 6: Put Special (RSI 70-100 extreme overbought on all TFs)
        pcr = 1.65
        for tf in REQUIRED_TIMEFRAMES:
            snapshots[tf] = IndicatorSnapshot(
                symbol="NIFTY",
                timeframe=tf,
                timestamp=now,
                close=24000.0,
                rsi=78.0,
                adx=38.0,
                plus_di=42.0,
                minus_di=8.0,
                bollinger_upper=24200.0,
                bollinger_middle=24000.0,
                bollinger_lower=23800.0,
                bollinger_bandwidth=0.06,
                bollinger_percent_b=0.95,
                psar=23850.0,
                psar_trend=1,
                chande_kroll_long=23900.0,
                chande_kroll_short=24250.0,
                ema_fast=24100.0,
                ema_slow=24000.0,
                ema_slope=3.5,
                ema_angle=35.0,
                rvol=3.0,
                vwap=23980.0,
                atr=68.0,
            )
    else:
        raise ValueError(f"Invalid case number: {case_num}")

    return snapshots, pcr


def _create_synthetic_option_chain(underlying_price: float = 24000.0) -> OptionChain:
    """Build synthetic NIFTY OptionChain around ATM strike with realistic OI and Greeks."""
    now = datetime.now(IST)
    expiry = date(2026, 8, 27)
    strikes = []
    for s in [23800.0, 23850.0, 23900.0, 23950.0, 24000.0, 24050.0, 24100.0, 24150.0, 24200.0]:
        dist = s - underlying_price
        ce_ltp = max(5.0, 120.0 - dist * 0.5)
        pe_ltp = max(5.0, 120.0 + dist * 0.5)

        ce_inst = Instrument(
            groww_symbol=f"NSE-NIFTY-2026-08-27-{int(s)}-CE",
            trading_symbol=f"NIFTY26AUG{int(s)}CE",
            name="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            lot_size=25,
            tick_size=0.05,
            expiry=expiry,
            strike_price=s,
            option_type=OptionType.CE,
        )
        pe_inst = Instrument(
            groww_symbol=f"NSE-NIFTY-2026-08-27-{int(s)}-PE",
            trading_symbol=f"NIFTY26AUG{int(s)}PE",
            name="NIFTY",
            exchange=Exchange.NSE,
            segment=Segment.FNO,
            lot_size=25,
            tick_size=0.05,
            expiry=expiry,
            strike_price=s,
            option_type=OptionType.PE,
        )

        strikes.append(
            OptionStrike(
                strike_price=s,
                call_instrument=ce_inst,
                call_ltp=round(ce_ltp, 2),
                call_bid=round(ce_ltp - 0.5, 2),
                call_ask=round(ce_ltp + 0.5, 2),
                call_oi=65000,
                call_volume=4500,
                put_instrument=pe_inst,
                put_ltp=round(pe_ltp, 2),
                put_bid=round(pe_ltp - 0.5, 2),
                put_ask=round(pe_ltp + 0.5, 2),
                put_oi=68000,
                put_volume=4800,
            )
        )

    return OptionChain.create(
        underlying_symbol="NIFTY",
        underlying_ltp=underlying_price,
        expiry_date=expiry,
        timestamp=now,
        strikes=strikes,
    )


@router.post("/{case_number}")
def simulate_case(case_number: int) -> dict[str, Any]:
    """Trigger real-time evaluation for any of the 6 strategy cases."""
    if case_number not in range(1, 7):
        raise HTTPException(status_code=400, detail="Case number must be between 1 and 6")

    snapshots, pcr = _create_synthetic_snapshots(case_number)
    match = evaluate_all_cases(snapshots, pcr)

    if match is None:
        raise HTTPException(
            status_code=500, detail=f"Case {case_number} conditions did not produce a match"
        )

    now = datetime.now(IST)
    underlying_price = 24000.0
    sig_id = f"sig-case{case_number}-{int(now.timestamp())}"

    # Build Signal
    sig = Signal(
        id=sig_id,
        symbol="NIFTY",
        case_number=match.case_number,
        created_at=now,
        status=SignalStatus.CREATED,
        signal_type=match.signal_type,
        underlying_price=underlying_price,
        pcr=pcr,
        strategy_version="0.1.0",
        reason=match.reason,
        indicators={tf.value: dataclasses.asdict(snapshots[tf]) for tf in REQUIRED_TIMEFRAMES},
    )

    # Run Contract Selector
    chain = _create_synthetic_option_chain(underlying_price)
    selector = OptionSelector(OptionSelectionPolicy())
    selection_result = selector.select(sig, chain)

    if selection_result.contract is not None:
        contracts = [selection_result.contract]
    elif selection_result.straddle is not None:
        contracts = [selection_result.straddle.call_contract, selection_result.straddle.put_contract]
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Option selection failed: {selection_result.message}",
        )

    # Inject into engine service (routes & broadcasts SSE)
    decision = engine_service.inject_signal(sig, contracts)

    return {
        "signal": {
            "id": sig.id,
            "symbol": sig.symbol,
            "case_number": sig.case_number,
            "signal_type": sig.signal_type.value,
            "pcr": sig.pcr,
            "underlying_price": sig.underlying_price,
            "reason": sig.reason,
            "status": sig.status.value,
            "routing_status": decision.status.value,
        },
        "indicators_summary": {
            tf.value: {
                "rsi": round(snapshots[tf].rsi, 2),
                "adx": round(snapshots[tf].adx, 2),
                "plus_di": round(snapshots[tf].plus_di, 2),
                "minus_di": round(snapshots[tf].minus_di, 2),
                "rvol": round(snapshots[tf].rvol, 2),
                "bb_percent_b": round(snapshots[tf].bollinger_percent_b, 2),
            }
            for tf in REQUIRED_TIMEFRAMES
        },
        "selected_contracts": [
            {
                "trading_symbol": c.trading_symbol,
                "strike": c.strike,
                "option_type": c.option_type.value,
                "expiry": str(c.expiry),
                "ltp": c.ltp,
                "lot_size": c.lot_size,
                "quantity": c.quantity,
                "order_value": round(c.ltp * c.quantity, 2),
                "open_interest": c.open_interest,
                "selection_reason": c.selection_reason,
            }
            for c in contracts
        ],
    }


@router.post("/run/all")
def simulate_all_cases() -> dict[str, Any]:
    """Simulate all 6 cases sequentially to verify complete strategy coverage."""
    results = []
    for c in range(1, 7):
        results.append(simulate_case(c))
    return {"total": len(results), "cases": results}
