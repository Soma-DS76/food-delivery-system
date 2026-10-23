from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    customer_id: int
    amount: Decimal
    payment_method: str
    provider: str
    provider_payment_id: str | None
    status: str
    created_at: datetime