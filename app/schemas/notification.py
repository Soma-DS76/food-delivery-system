
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    notification_type: str
    order_id: int | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class UnreadCountResponse(BaseModel):
    unread_count: int
