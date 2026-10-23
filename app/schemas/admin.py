from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str
    is_active: bool
    is_approved: bool


class UserStatusUpdate(BaseModel):
    is_active: bool


class RestaurantApprovalUpdate(BaseModel):
    is_approved: bool


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int
    action: str
    target_type: str
    target_id: int
    details: str | None
    created_at: datetime