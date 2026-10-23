
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class CheckoutRequest(BaseModel):
    address_id: int = Field(gt=0)
    payment_method: Literal["COD", "ONLINE"] = "COD"
    tip_amount: Decimal = Field( default=Decimal("0.00"), ge=0, le=500, max_digits=10, decimal_places=2 )


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    item_name: str
    quantity: int
    unit_price: Decimal
    packaging_charge: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    customer_id: int
    restaurant_id: int
    address_id: int
    item_total: Decimal
    coupon_code: str | None
    discount_amount: Decimal
    packaging_charges: Decimal
    delivery_fee: Decimal
    platform_fee: Decimal
    gst_amount: Decimal
    tip_amount: Decimal
    grand_total: Decimal
    payment_method: str
    payment_status: str
    status: str
    distance_km: float
    placed_at: datetime
    items: list[OrderItemResponse]


class OrderSummaryResponse(BaseModel):
    id: int
    order_number: str
    restaurant_id: int
    grand_total: Decimal
    payment_method: str
    payment_status: str
    status: str
    placed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    old_status: str | None
    new_status: str
    changed_by: str
    changed_at: datetime
