"""Orders API endpoints."""

from fastapi import APIRouter

from ..schemas.orders import OrderListResponse, OrderResponseModel
from ..services.engine_service import engine_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("", response_model=OrderListResponse)
def list_orders() -> OrderListResponse:
    """Return all executed and open orders."""
    orders = engine_service.get_orders()
    items = [
        OrderResponseModel(
            order_id=o.order_id,
            groww_symbol=o.groww_symbol,
            status=o.status.value,
            filled_quantity=o.filled_quantity,
            average_price=o.average_price,
            message=o.message,
        )
        for o in orders
    ]
    return OrderListResponse(total=len(items), orders=items)
