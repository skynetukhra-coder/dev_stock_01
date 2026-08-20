"""Order request and response schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class OrderResponseModel(BaseModel):
    order_id: str
    groww_symbol: str
    status: str
    filled_quantity: int = 0
    average_price: float = 0.0
    message: Optional[str] = None


class OrderListResponse(BaseModel):
    total: int
    orders: list[OrderResponseModel]
