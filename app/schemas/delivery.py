
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AvailabilityUpdate(BaseModel):
    is_online: bool


class LocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class DeliveryOTP(BaseModel):
    otp: str = Field(pattern=r"^\d{4}$")


class OfferResponse(BaseModel):
    id: int
    order_id: int
    status: str
    offered_at: datetime
    expires_at: datetime


class EarningsResponse(BaseModel):
    from_date: date
    to_date: date
    delivery_count: int
    total_earnings: Decimal
