
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import ( BaseModel, Field, ConfigDict, model_validator )


class CouponCreate(BaseModel):

    code: str = Field( min_length=3, max_length=60, pattern=r"^[A-Za-z0-9_-]+$" )
    description: str | None = None
    discount_type: Literal["percentage", "flat"]
    discount_value: Decimal = Field(gt=0)
    max_discount: Decimal | None = Field( default=None, gt=0 )
    min_order_value: Decimal = Field( default=Decimal("0.00"), ge=0 )
    restaurant_id: int | None = Field( default=None, gt=0 )
    valid_from: datetime
    valid_to: datetime
    total_usage_limit: int | None = Field( default=None, gt=0 )
    per_user_limit: int | None = Field( default=None, gt=0 )
    first_order_only: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_coupon(self):
        if self.valid_from >= self.valid_to:
            raise ValueError( "valid_to must be after valid_from" )

        if ( self.discount_type == "percentage" and self.discount_value > 100 ):
            raise ValueError( "Percentage discount cannot exceed 100" )

        return self


class CouponUpdate(BaseModel):
    description: str | None = None
    valid_to: datetime | None = None
    total_usage_limit: int | None = Field( default=None, gt=0 )
    per_user_limit: int | None = Field( default=None, gt=0 )
    is_active: bool | None = None


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: str | None
    discount_type: str
    discount_value: Decimal
    max_discount: Decimal | None
    min_order_value: Decimal
    restaurant_id: int | None
    valid_from: datetime
    valid_to: datetime
    total_usage_limit: int | None
    per_user_limit: int | None
    first_order_only: bool
    is_active: bool


class ApplyCouponRequest(BaseModel):
    code: str = Field(min_length=1, max_length=60)
