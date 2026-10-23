
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User
from app.auth.security import require_roles
from app.schemas.auth import UserResponse
from app.routers.auth import serialize_user

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.put( "/users/{user_id}/approve", response_model=UserResponse )
def approve_user( user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    user = db.get(User, user_id)

    if not user:
        raise HTTPException( status_code=404, detail="User not found" )

    role = getattr(user.role, "value", user.role)

    if role not in ["restaurant_owner", "delivery_partner"]:
        raise HTTPException( status_code=400, detail="Only restaurant owners and delivery partners require approval" )

    if not user.is_active:
        raise HTTPException( status_code=400, detail="Cannot approve an inactive account" )

    user.is_approved = True
    db.commit()
    db.refresh(user)

    return serialize_user(user)
