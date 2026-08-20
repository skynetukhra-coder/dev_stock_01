"""Risk status and Emergency Kill switch endpoints."""

from datetime import datetime

from fastapi import APIRouter
from prophecy_engine.market.sessions import IST, is_market_open

from ..schemas.risk import KillSwitchRequest, KillSwitchResponse, RiskStatusResponse
from ..services.engine_service import engine_service

router = APIRouter(tags=["Risk Controls"])


@router.get("/risk/status", response_model=RiskStatusResponse)
def get_risk_status() -> RiskStatusResponse:
    """Return live risk limits and loss utilization."""
    acc = engine_service.paper_account
    pol = engine_service.risk_manager.default_policy
    now = datetime.now(IST)

    return RiskStatusResponse(
        kill_switch_active=engine_service.risk_manager.is_kill_switch_active,
        daily_realized_pnl=acc.realized_pnl,
        daily_unrealized_pnl=acc.unrealized_pnl,
        open_positions_count=len(engine_service.get_positions()),
        max_open_positions=pol.max_open_positions,
        max_daily_realized_loss=pol.max_daily_realized_loss,
        max_daily_total_loss=pol.max_daily_total_loss,
        is_market_open=is_market_open(now),
    )


@router.post("/kill-switch", response_model=KillSwitchResponse)
def toggle_kill_switch(req: KillSwitchRequest) -> KillSwitchResponse:
    """Emergency halt toggle: blocks all new entries immediately."""
    active = engine_service.toggle_kill_switch(req.active, operator_id=req.operator_id)
    msg = (
        "Emergency kill switch activated. All new entries blocked."
        if active
        else "Emergency kill switch deactivated."
    )
    return KillSwitchResponse(active=active, message=msg)
