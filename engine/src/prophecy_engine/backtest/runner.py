"""Backtest execution runner, multi-timeframe candle replayer and position manager."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Mapping, Optional, Sequence

from ..domain.enums import RiskAction, SignalType
from ..domain.models import Signal
from ..market.candles import Candle, CandleSeries, Timeframe
from ..market.instruments import Exchange, InstrumentMaster, OptionType, Segment
from ..market.option_chain import OptionChain, OptionStrike
from ..market.sessions import to_ist
from ..risk.manager import RiskContext, RiskManager, RiskPolicy
from ..strategy.cases import REQUIRED_TIMEFRAMES
from ..strategy.option_selector import (
    OptionSelectionPolicy,
    OptionSelector,
    SelectedContract,
)
from ..strategy.signal_engine import SignalEngine, StrategyConfig
from .costs import SlippageModel, TransactionCostModel
from .metrics import BacktestMetrics, calculate_metrics
from .models import BacktestTrade, ExitReason


@dataclass(frozen=True)
class BacktestConfig:
    """Configuration settings for backtest execution."""

    initial_capital: float = 100000.0
    stop_loss_pct: float = 0.20  # 20% stop loss on option premium
    take_profit_pct: float = 0.40  # 40% take profit target
    square_off_time: time = time(15, 15)  # 15:15 IST auto square-off
    slippage_pct: float = 0.001  # 0.10% slippage
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)
    risk_policy: RiskPolicy = field(default_factory=RiskPolicy)
    option_policy: OptionSelectionPolicy = field(default_factory=OptionSelectionPolicy)
    cost_model: TransactionCostModel = field(default_factory=TransactionCostModel)


@dataclass
class _ActivePosition:
    trade_id: str
    signal_id: str
    symbol: str
    case_number: int
    signal_type: SignalType
    contract: SelectedContract
    entry_time: datetime
    entry_price: float
    quantity: int
    delta: float = 0.5


class BacktestRunner:
    """Replays historical multi-timeframe candles and simulates strategy execution."""

    def __init__(self, config: Optional[BacktestConfig] = None) -> None:
        self.config = config or BacktestConfig()
        self.signal_engine = SignalEngine(config=self.config.strategy_config)
        self.option_selector = OptionSelector(default_policy=self.config.option_policy)
        self.risk_manager = RiskManager(default_policy=self.config.risk_policy)
        self.slippage_model = SlippageModel(slippage_pct=self.config.slippage_pct)

    def run(
        self,
        symbol: str,
        multi_tf_candles: Mapping[Timeframe, Sequence[Candle]],
        pcr_series: Optional[Mapping[datetime, float]] = None,
        instrument_master: Optional[InstrumentMaster] = None,
    ) -> tuple[list[BacktestTrade], BacktestMetrics]:
        """Run synchronized backtest over candle series."""
        # 1. Validate that all required timeframes exist
        for tf in REQUIRED_TIMEFRAMES:
            if tf not in multi_tf_candles or len(multi_tf_candles[tf]) < 30:
                return [], calculate_metrics([], self.config.initial_capital)

        # Primary iteration based on 1m candles
        m1_candles = multi_tf_candles[Timeframe.M1]
        completed_trades: list[BacktestTrade] = []
        active_positions: list[_ActivePosition] = []

        # Replay simulation state
        daily_realized_pnl = 0.0
        symbol_signals_today: dict[str, int] = {}
        recent_signals: list[Signal] = []
        last_date: Optional[date] = None

        # Minimum warm-up window for indicator stabilization
        warmup_len = 35

        for step_idx in range(warmup_len, len(m1_candles)):
            curr_candle = m1_candles[step_idx]
            curr_time = to_ist(curr_candle.timestamp)
            curr_date = curr_time.date()

            # Daily reset on new session day
            if last_date is None or curr_date != last_date:
                daily_realized_pnl = 0.0
                symbol_signals_today.clear()
                recent_signals.clear()
                last_date = curr_date

            # Build synchronized window slice for each timeframe up to curr_time
            slice_series: dict[Timeframe, CandleSeries] = {}
            for tf in REQUIRED_TIMEFRAMES:
                tf_candles = [c for c in multi_tf_candles[tf] if to_ist(c.timestamp) <= curr_time]
                if len(tf_candles) < 20:
                    break
                slice_series[tf] = CandleSeries.create(symbol, tf, tf_candles)

            if len(slice_series) < len(REQUIRED_TIMEFRAMES):
                continue

            curr_spot = curr_candle.close
            curr_pcr = pcr_series.get(curr_time, 1.0) if pcr_series else 1.0

            # Step A: Manage and update existing active positions
            remaining_positions: list[_ActivePosition] = []
            for pos in active_positions:
                # Approximate option LTP evolution from spot movement
                spot_entry = pos.contract.strike  # Base spot proxy
                spot_change = curr_spot - spot_entry
                opt_change = spot_change * pos.delta
                if pos.contract.option_type == OptionType.PE:
                    opt_change = -spot_change * pos.delta

                sim_ltp = max(0.05, pos.entry_price + opt_change)

                exit_reason = None
                # 1. Stop Loss
                if sim_ltp <= pos.entry_price * (1.0 - self.config.stop_loss_pct):
                    exit_reason = ExitReason.STOP_LOSS
                # 2. Take Profit
                elif sim_ltp >= pos.entry_price * (1.0 + self.config.take_profit_pct):
                    exit_reason = ExitReason.TAKE_PROFIT
                # 3. Session square-off
                elif curr_time.time() >= self.config.square_off_time:
                    exit_reason = ExitReason.SESSION_END

                if exit_reason is not None:
                    # Execute position exit with sell slippage
                    fill_exit_price = self.slippage_model.apply_sell(sim_ltp)
                    gross_pnl = (fill_exit_price - pos.entry_price) * pos.quantity
                    costs = self.config.cost_model.calculate_costs(
                        buy_price=pos.entry_price,
                        sell_price=fill_exit_price,
                        quantity=pos.quantity,
                    )
                    net_pnl = gross_pnl - costs.total_cost
                    daily_realized_pnl += net_pnl
                    duration_min = (curr_time - pos.entry_time).total_seconds() / 60.0

                    trade = BacktestTrade(
                        trade_id=pos.trade_id,
                        signal_id=pos.signal_id,
                        symbol=pos.symbol,
                        case_number=pos.case_number,
                        signal_type=pos.signal_type,
                        contract_symbol=pos.contract.groww_symbol,
                        entry_time=pos.entry_time,
                        entry_price=pos.entry_price,
                        exit_time=curr_time,
                        exit_price=fill_exit_price,
                        quantity=pos.quantity,
                        gross_pnl=round(gross_pnl, 2),
                        net_pnl=round(net_pnl, 2),
                        costs=costs,
                        exit_reason=exit_reason,
                        holding_duration_minutes=round(duration_min, 1),
                    )
                    completed_trades.append(trade)
                else:
                    remaining_positions.append(pos)

            active_positions = remaining_positions

            # Step B: Evaluate potential entry if no active position in symbol
            if len(active_positions) == 0 and curr_time.time() < self.config.square_off_time:
                signal = self.signal_engine.evaluate(
                    symbol=symbol,
                    multi_tf_series=slice_series,
                    pcr=curr_pcr,
                    underlying_price=curr_spot,
                    timestamp=curr_time,
                )

                if signal is not None:
                    # Synthesize ATM Option Chain for contract selection
                    atm_strike = round(curr_spot / 50.0) * 50.0
                    chain = self._build_synthetic_chain(
                        symbol=symbol,
                        spot=curr_spot,
                        atm_strike=atm_strike,
                        timestamp=curr_time,
                    )

                    sel_res = self.option_selector.select(
                        signal=signal,
                        option_chain=chain,
                        instrument_master=instrument_master,
                        reference_date=curr_date,
                    )

                    if sel_res.is_success and sel_res.contract is not None:
                        contract = sel_res.contract
                        # Risk evaluation
                        risk_ctx = RiskContext(
                            daily_realized_pnl=daily_realized_pnl,
                            open_positions=[],
                            symbol_signal_counts=symbol_signals_today,
                            recent_signals=recent_signals,
                            current_time=curr_time,
                        )
                        risk_eval = self.risk_manager.evaluate_entry(
                            signal, contract, risk_ctx, self.config.risk_policy
                        )

                        if risk_eval.action == RiskAction.ALLOW:
                            # Fill entry with buy slippage
                            fill_entry_price = self.slippage_model.apply_buy(contract.ltp)
                            trade_id = f"trd-{uuid.uuid4().hex[:10]}"
                            active_positions.append(
                                _ActivePosition(
                                    trade_id=trade_id,
                                    signal_id=signal.id,
                                    symbol=symbol,
                                    case_number=signal.case_number,
                                    signal_type=signal.signal_type,
                                    contract=contract,
                                    entry_time=curr_time,
                                    entry_price=fill_entry_price,
                                    quantity=contract.quantity,
                                    delta=0.5,
                                )
                            )
                            symbol_signals_today[symbol] = symbol_signals_today.get(symbol, 0) + 1
                            recent_signals.append(signal)

        # Step C: Force-close remaining positions at final step
        if active_positions and len(m1_candles) > 0:
            final_candle = m1_candles[-1]
            final_time = to_ist(final_candle.timestamp)
            for pos in active_positions:
                fill_exit = self.slippage_model.apply_sell(pos.contract.ltp)
                gross = (fill_exit - pos.entry_price) * pos.quantity
                costs = self.config.cost_model.calculate_costs(
                    buy_price=pos.entry_price,
                    sell_price=fill_exit,
                    quantity=pos.quantity,
                )
                net = gross - costs.total_cost
                duration = (final_time - pos.entry_time).total_seconds() / 60.0
                trade = BacktestTrade(
                    trade_id=pos.trade_id,
                    signal_id=pos.signal_id,
                    symbol=pos.symbol,
                    case_number=pos.case_number,
                    signal_type=pos.signal_type,
                    contract_symbol=pos.contract.groww_symbol,
                    entry_time=pos.entry_time,
                    entry_price=pos.entry_price,
                    exit_time=final_time,
                    exit_price=fill_exit,
                    quantity=pos.quantity,
                    gross_pnl=round(gross, 2),
                    net_pnl=round(net, 2),
                    costs=costs,
                    exit_reason=ExitReason.SESSION_END,
                    holding_duration_minutes=round(duration, 1),
                )
                completed_trades.append(trade)

        metrics = calculate_metrics(completed_trades, self.config.initial_capital)
        return completed_trades, metrics

    def _build_synthetic_chain(
        self,
        symbol: str,
        spot: float,
        atm_strike: float,
        timestamp: datetime,
    ) -> OptionChain:
        """Create synthetic liquid option chain centered around spot ATM strike."""
        exp_date = timestamp.date()
        strikes = []
        for offset in [-100.0, -50.0, 0.0, 50.0, 100.0]:
            k = atm_strike + offset
            ce_ltp = max(5.0, 120.0 - (k - spot) * 0.5)
            pe_ltp = max(5.0, 120.0 + (k - spot) * 0.5)
            strikes.append(
                OptionStrike(
                    strike_price=k,
                    call_ltp=round(ce_ltp, 2),
                    call_oi=50000,
                    call_volume=2500,
                    call_bid=round(ce_ltp - 0.5, 2),
                    call_ask=round(ce_ltp + 0.5, 2),
                    put_ltp=round(pe_ltp, 2),
                    put_oi=55000,
                    put_volume=2600,
                    put_bid=round(pe_ltp - 0.5, 2),
                    put_ask=round(pe_ltp + 0.5, 2),
                )
            )

        return OptionChain(
            underlying_symbol=symbol,
            underlying_ltp=spot,
            expiry_date=exp_date,
            timestamp=timestamp,
            strikes=tuple(strikes),
            exchange=Exchange.NSE,
            segment=Segment.FNO,
        )
