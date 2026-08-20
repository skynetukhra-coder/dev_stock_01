"""SignalEngine orchestrator for multi-timeframe strategy evaluation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from ..domain.enums import SignalStatus
from ..domain.models import Signal
from ..indicators.engine import IndicatorEngine, IndicatorSnapshot
from ..market.candles import CandleSeries, Timeframe
from ..market.sessions import IST, to_ist
from .cases import REQUIRED_TIMEFRAMES, evaluate_all_cases


@dataclass(frozen=True)
class StrategyConfig:
    """Configurable strategy parameters and thresholds."""

    strategy_version: str = "0.1.0"
    call_pcr_max: float = 0.8
    put_pcr_min: float = 1.25
    enabled_cases: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
    required_timeframes: tuple[Timeframe, ...] = REQUIRED_TIMEFRAMES


class SignalEngine:
    """Evaluates multi-timeframe candle series and PCR against strategy cases."""

    def __init__(
        self,
        config: Optional[StrategyConfig] = None,
        indicator_engine: Optional[IndicatorEngine] = None,
    ) -> None:
        self.config = config or StrategyConfig()
        self.indicator_engine = indicator_engine or IndicatorEngine()

    def evaluate(
        self,
        symbol: str,
        multi_tf_series: Mapping[Timeframe, CandleSeries],
        pcr: float,
        underlying_price: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Signal]:
        """Evaluate strategy across all required timeframes.

        Returns a Signal if a valid case is met, or None (NO_SIGNAL).
        """
        # Step 1: Ensure all required timeframes are present
        for tf in self.config.required_timeframes:
            if tf not in multi_tf_series:
                return None
            if len(multi_tf_series[tf]) == 0:
                return None

        # Step 2: Compute indicator snapshots for each timeframe
        snapshots: dict[Timeframe, IndicatorSnapshot] = {}
        for tf in self.config.required_timeframes:
            series = multi_tf_series[tf]
            try:
                snapshot = self.indicator_engine.compute_snapshot(series)
                if not snapshot.is_valid():
                    return None
                snapshots[tf] = snapshot
            except Exception:
                return None

        # Step 3: Evaluate strategy cases
        match = evaluate_all_cases(
            snapshots=snapshots,
            pcr=pcr,
            call_pcr_max=self.config.call_pcr_max,
            put_pcr_min=self.config.put_pcr_min,
            required_timeframes=self.config.required_timeframes,
        )

        if match is None or match.case_number not in self.config.enabled_cases:
            return None

        # Step 4: Construct verified immutable Signal
        sig_time = to_ist(timestamp or datetime.now(IST))
        sig_id = f"sig-{uuid.uuid4().hex[:12]}"

        # Serialized snapshot metadata for auditing
        indicators_map: dict[str, Any] = {
            tf.value: {
                "close": snapshots[tf].close,
                "rsi": snapshots[tf].rsi,
                "adx": snapshots[tf].adx,
                "plus_di": snapshots[tf].plus_di,
                "minus_di": snapshots[tf].minus_di,
                "bollinger_upper": snapshots[tf].bollinger_upper,
                "bollinger_lower": snapshots[tf].bollinger_lower,
                "psar": snapshots[tf].psar,
            }
            for tf in self.config.required_timeframes
        }

        return Signal(
            id=sig_id,
            symbol=symbol.upper(),
            case_number=match.case_number,
            created_at=sig_time,
            status=SignalStatus.CREATED,
            signal_type=match.signal_type,
            underlying_price=underlying_price,
            pcr=pcr,
            strategy_version=self.config.strategy_version,
            reason=match.reason,
            indicators=indicators_map,
        )
