"""Backtest API endpoint."""

from fastapi import APIRouter

from ..schemas.backtest import BacktestRequest, BacktestResponse
from ..services.engine_service import engine_service

router = APIRouter(prefix="/backtest", tags=["Backtesting"])


@router.post("", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest) -> BacktestResponse:
    """Trigger multi-timeframe backtest simulation and return performance report."""
    results = engine_service.run_backtest(
        symbol=req.symbol,
        initial_capital=req.initial_capital,
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        slippage_pct=req.slippage_pct,
    )
    return BacktestResponse(**results)
