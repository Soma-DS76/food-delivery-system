
from datetime import time, datetime
from decimal import Decimal

from pydantic import ( BaseModel,Field,ConfigDict,model_validator )


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    cuisine_type: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=5)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    opening_time: time
    closing_time: time

    delivery_radius_km: float = Field(default=5, gt=0)
    min_order_value: Decimal = Field(default=0, ge=0)
    avg_preparation_minutes: int = Field(default=30, gt=0)

    @model_validator(mode="after")
    def validate_times(self):
        if self.opening_time >= self.closing_time:
            raise ValueError( "Opening time must be before closing time" )
        return self


class RestaurantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    cuisine_type: str | None = Field(default=None, min_length=2, max_length=80)
    address: str | None = Field(default=None, min_length=5)

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    opening_time: time | None = None
    closing_time: time | None = None

    delivery_radius_km: float | None = Field(default=None, gt=0)
    min_order_value: Decimal | None = Field(default=None, ge=0)
    avg_preparation_minutes: int | None = Field(default=None, gt=0)


class RestaurantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    cuisine_type: str
    address: str
    latitude: float
    longitude: float
    opening_time: time
    closing_time: time
    is_temporarily_closed: bool
    delivery_radius_km: float
    min_order_value: Decimal
    avg_preparation_minutes: int
    average_rating: float
    is_active: bool
    is_open: bool
    created_at: datetime


class OpenStatusUpdate(BaseModel):
    is_temporarily_closed: bool


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int
    name: str


class MenuItemCreate(BaseModel):
    category_id: int
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    is_veg: bool
    packaging_charge: Decimal = Field( default=0, ge=0, max_digits=10, decimal_places=2)
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    price: Decimal | None = Field( default=None, gt=0, max_digits=10, decimal_places=2)
    is_veg: bool | None = None
    packaging_charge: Decimal | None = Field( default=None, ge=0, max_digits=10, decimal_places=2)


class MenuItemResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int
    category_id: int
    name: str
    description: str | None
    price: Decimal
    is_veg: bool
    packaging_charge: Decimal
    is_available: bool


class AvailabilityUpdate(BaseModel):
    is_available: bool


class MenuCategoryWithItems(CategoryResponse):
    items: list[MenuItemResponse] = []


class RestaurantMenuResponse(BaseModel):
    restaurant_id: int
    restaurant_name: str
    categories: list[MenuCategoryWithItems]
