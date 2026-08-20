"""Positions and Account summary API endpoints."""

from fastapi import APIRouter

from ..schemas.positions import AccountSummaryResponse, PositionModel
from ..services.engine_service import engine_service

router = APIRouter(tags=["Positions & Ledger"])


@router.get("/positions", response_model=list[PositionModel])
def list_positions() -> list[PositionModel]:
    """Return all active portfolio positions."""
    positions = engine_service.get_positions()
    return [
        PositionModel(
            groww_symbol=p.groww_symbol,
            quantity=p.quantity,
            average_price=p.average_price,
            ltp=p.ltp,
            pnl=p.pnl,
            realized_pnl=p.realized_pnl,
            unrealized_pnl=p.unrealized_pnl,
        )
        for p in positions
    ]


@router.get("/account/summary", response_model=AccountSummaryResponse)
def get_account_summary() -> AccountSummaryResponse:
    """Return cash balance, portfolio value, equity, and P&L ledger."""
    summary = engine_service.get_account_summary()
    return AccountSummaryResponse(**summary)
