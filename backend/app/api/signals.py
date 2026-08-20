"""Signals API endpoints."""

from fastapi import APIRouter, HTTPException, status

from ..schemas.signals import (
    ConfirmSignalRequest,
    IgnoreSignalRequest,
    SignalListResponse,
    SignalResponse,
)
from ..services.engine_service import engine_service

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("", response_model=SignalListResponse)
def list_signals() -> SignalListResponse:
    """Return all active and historical signals."""
    sigs = engine_service.list_signals()
    items = [
        SignalResponse(
            id=s.id,
            symbol=s.symbol,
            case_number=s.case_number,
            created_at=s.created_at,
            status=s.status.value,
            signal_type=s.signal_type.value,
            underlying_price=s.underlying_price,
            pcr=s.pcr,
            strategy_version=s.strategy_version,
            reason=s.reason,
            indicators=s.indicators,
        )
        for s in sigs
    ]
    return SignalListResponse(total=len(items), signals=items)


@router.get("/{signal_id}", response_model=SignalResponse)
def get_signal(signal_id: str) -> SignalResponse:
    """Fetch details for a specific signal ID."""
    s = engine_service.get_signal(signal_id)
    if s is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found",
        )
    return SignalResponse(
        id=s.id,
        symbol=s.symbol,
        case_number=s.case_number,
        created_at=s.created_at,
        status=s.status.value,
        signal_type=s.signal_type.value,
        underlying_price=s.underlying_price,
        pcr=s.pcr,
        strategy_version=s.strategy_version,
        reason=s.reason,
        indicators=s.indicators,
    )


@router.post("/{signal_id}/confirm")
def confirm_signal(signal_id: str, req: ConfirmSignalRequest) -> dict:
    """Confirm a pending signal and trigger execution."""
    decision = engine_service.confirm_signal(signal_id, operator_id=req.operator_id)
    if decision.status.value == "ERROR":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=decision.message,
        )
    return {
        "status": decision.status.value,
        "signal_id": signal_id,
        "message": decision.message,
        "orders_count": len(decision.order_responses),
    }


@router.post("/{signal_id}/ignore")
def ignore_signal(signal_id: str, req: IgnoreSignalRequest) -> dict:
    """Ignore/reject a pending signal."""
    success = engine_service.ignore_signal(
        signal_id, operator_id=req.operator_id, reason=req.reason
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not ignore signal {signal_id}",
        )
    return {"status": "IGNORED", "signal_id": signal_id, "reason": req.reason}
