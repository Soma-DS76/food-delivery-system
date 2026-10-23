
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class AddCartItemRequest(BaseModel):

    menu_item_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=10)


class UpdateCartItemRequest(BaseModel):
    
    quantity: int = Field(ge=1, le=10)


class CartItemResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int
    name: str
    quantity: int
    unit_price: Decimal
    packaging_charge: Decimal
    line_total: Decimal
    is_available: bool


class CartResponse(BaseModel):

    cart_id: int | None = None
    restaurant_id: int | None = None
    restaurant_name: str | None = None
    items: list[CartItemResponse] = Field( default_factory=list)
    item_total: Decimal = Decimal("0.00")
    packaging_total: Decimal = Decimal("0.00")
    coupon_code: str | None = None
    discount_amount: Decimal = Decimal("0.00")
    item_total_after_discount: Decimal = Decimal("0.00")
    grand_total: Decimal = Decimal("0.00")
