from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (User,Restaurant,Order,AuditLog)


def write_audit_log(db: Session,admin_id: int,action: str,target_type: str,target_id: int,details: str | None = None):
    db.add(AuditLog(actor_user_id=admin_id,action=action,target_type=target_type,target_id=target_id,details=details))


def list_users(db: Session, limit: int = 50, offset: int = 0):
    statement = (select(User).order_by(User.id.desc()).limit(limit).offset(offset))
    return list(db.scalars(statement).all())


def update_user_status(db: Session,admin_id: int,user_id: int,is_active: bool):
    try:
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())

        if user is None:
            raise HTTPException(404, "User not found")

        if user.id == admin_id and not is_active:
            raise HTTPException(400,"You cannot deactivate your own admin account")

        user.is_active = is_active

        write_audit_log(db,admin_id,"user_status_updated","user",user.id,f"is_active={is_active}")

        db.commit()
        db.refresh(user)
        return user

    except Exception:
        db.rollback()
        raise


def approve_restaurant_owner(db: Session,admin_id: int,owner_id: int,is_approved: bool):
    try:
        owner = db.scalar(select(User).where(User.id == owner_id).with_for_update())

        if owner is None:
            raise HTTPException(404, "User not found")

        if owner.role != "restaurant_owner":
            raise HTTPException(400,"User is not a restaurant owner")

        owner.is_approved = is_approved

        write_audit_log(db,admin_id,"restaurant_owner_approval_updated","user",owner.id,
                        f"is_approved={is_approved}")

        db.commit()
        db.refresh(owner)
        return owner

    except Exception:
        db.rollback()
        raise


def list_restaurants(db: Session, limit: int = 50, offset: int = 0):
    statement = (select(Restaurant).order_by(Restaurant.id.desc()).limit(limit).offset(offset))
    return list(db.scalars(statement).all())


def get_admin_statistics(db: Session):
    users = list(db.scalars(select(User)).all())
    restaurants = list(db.scalars(select(Restaurant)).all())
    orders = list(db.scalars(select(Order)).all())

    return {"total_users": len(users),
            "active_users": sum(1 for u in users if u.is_active),
            "total_customers": sum(1 for u in users if u.role == "customer"),
            "total_restaurants": len(restaurants),
            "active_restaurants": sum(1 for r in restaurants if r.is_active),
            "total_orders": len(orders)}