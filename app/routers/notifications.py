
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import get_current_user
from app.models.entities import User, Notification
from app.schemas.notification import (NotificationResponse,UnreadCountResponse)


router = APIRouter(prefix="/notifications",tags=["Notifications"])


@router.get( "",response_model=list[NotificationResponse])
def list_notifications(unread_only: bool = False,limit: int = Query(default=20, ge=1, le=100),offset: int = Query(default=0, ge=0),
                       db: Session = Depends(get_db),user: User = Depends(get_current_user)):
    query = select(Notification).where(Notification.user_id == user.id)

    if unread_only:query = query.where(Notification.is_read.is_(False))

    query = query.order_by(Notification.created_at.desc(),Notification.id.desc()).offset(offset).limit(limit)

    return db.scalars(query).all()


@router.get("/unread-count",response_model=UnreadCountResponse)
def unread_count(db: Session = Depends(get_db),user: User = Depends(get_current_user),):
    count = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id,Notification.is_read.is_(False)))

    return {"unread_count": count or 0}


@router.put("/{notification_id}/read")
def mark_as_read(notification_id: int,db: Session = Depends(get_db),user: User = Depends(get_current_user)):
    notification = db.scalar( select(Notification).where(Notification.id == notification_id,
                                                         Notification.user_id == user.id))

    if notification is None:
        raise HTTPException(404, "Notification not found")

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc).replace(tzinfo=None)

        db.commit()

    return {"message": "Notification marked as read"}


@router.put("/read-all")
def mark_all_as_read(db: Session = Depends(get_db),user: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    result = db.execute(update(Notification)
                        .where(Notification.user_id == user.id,Notification.is_read.is_(False))
                        .values(is_read=True,read_at=now))

    db.commit()

    return { "message": "All notifications marked as read","updated_count": result.rowcount }
