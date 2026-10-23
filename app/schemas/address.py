
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AddressCreate(BaseModel):
    label: str = Field( min_length=2, max_length=30, examples=["Home"] )

    address_line: str = Field(min_length=5)
    city: str = Field(min_length=2, max_length=100)
    pincode: str = Field(pattern=r"^[0-9]{6}$")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    is_default: bool = False


class AddressUpdate(BaseModel):
    label: str | None = Field( default=None, min_length=2, max_length=30 )
    address_line: str | None = Field( default=None, min_length=5 )
    city: str | None = Field( default=None, min_length=2, max_length=100 )
    pincode: str | None = Field( default=None, pattern=r"^[0-9]{6}$" )
    latitude: float | None = Field( default=None, ge=-90, le=90 )
    longitude: float | None = Field( default=None, ge=-180, le=180 )
    is_default: bool | None = None


class AddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    label: str
    address_line: str
    city: str
    pincode: str
    latitude: float
    longitude: float
    is_default: bool
    created_at: datetime
