
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RejectOrderRequest(BaseModel):
    reason: str = Field( min_length=5, max_length=300 )


class RestaurantOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    item_name: str
    quantity: int
    unit_price: Decimal
    packaging_charge: Decimal


class RestaurantOrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    customer_id: int
    restaurant_id: int
    status: str
    payment_method: str
    payment_status: str
    grand_total: Decimal
    placed_at: datetime


class RestaurantOrderDetail(RestaurantOrderSummary):
    address_id: int
    item_total: Decimal
    coupon_code: str | None
    discount_amount: Decimal
    packaging_charges: Decimal
    delivery_fee: Decimal
    platform_fee: Decimal
    gst_amount: Decimal
    tip_amount: Decimal
    distance_km: float
    items: list[RestaurantOrderItemResponse]


class RestaurantOrderHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    old_status: str | None
    new_status: str
    changed_by: str
    changed_at: datetime
