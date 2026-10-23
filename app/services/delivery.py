
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.entities import (User, Restaurant, Order, DeliveryPartner,DeliveryOffer, OrderStatusHistory)


ACTIVE_STATUSES = ( "Accepted", "Preparing", "ReadyForPickup","PickedUp", "OutForDelivery")


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def distance_km(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt

    a1, a2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    value = ( sin(dlat / 2) ** 2+ cos(a1) * cos(a2) * sin(dlon / 2) ** 2)
    return 6371 * 2 * asin(min(1, sqrt(value)))


def get_partner(db: Session, user: User):
    if not user.is_approved:
        raise HTTPException(403, "Admin approval required")

    partner = db.scalar(select(DeliveryPartner).where( DeliveryPartner.user_id == user.id))

    if not partner or not partner.is_approved:
        raise HTTPException(403, "Partner not approved")

    return partner


def has_active_delivery(db: Session, partner_id: int):
    return db.scalar(
        select(Order.id).where(Order.delivery_partner_id == partner_id,
                               Order.status.in_(ACTIVE_STATUSES)).limit(1)) is not None


def assign_next_partner(db: Session, order_id: int):
    """
    Call within an existing transaction.
    Caller must hold the order row lock.
    """
    order = db.get(Order, order_id)

    if not order or order.delivery_partner_id:
        return None

    if order.status not in ("Accepted", "Preparing", "ReadyForPickup"):
        return None

    existing = db.scalar(select(DeliveryOffer.id).where(DeliveryOffer.order_id == order_id,
                                                        DeliveryOffer.status == "Pending",
                                                        DeliveryOffer.expires_at > now_utc()))
    if existing:
        return None

    restaurant = db.get(Restaurant, order.restaurant_id)

    if restaurant is None:
        return None

    excluded = select(DeliveryOffer.partner_id).where(DeliveryOffer.order_id == order_id)

    partners = db.scalars(select(DeliveryPartner)
                          .join(User, User.id == DeliveryPartner.user_id)
                          .where(   DeliveryPartner.is_approved.is_(True),
                                    DeliveryPartner.is_online.is_(True),
                                    User.is_active.is_(True),
                                    DeliveryPartner.current_latitude.is_not(None),
                                    DeliveryPartner.current_longitude.is_not(None),
                                    DeliveryPartner.id.not_in(excluded))).all()

    eligible = []

    for partner in partners:
        if has_active_delivery(db, partner.id):
            continue

        km = distance_km(restaurant.latitude,restaurant.longitude,partner.current_latitude,partner.current_longitude)

        if km <= 5:
            eligible.append((km, partner))

    eligible.sort(key=lambda item: item[0])

    if not eligible:
        return None

    partner = eligible[0][1]

    offer = DeliveryOffer(order_id=order.id,partner_id=partner.id,status="Pending",offered_at=now_utc(),expires_at=now_utc() + timedelta(seconds=30))

    db.add(offer)
    db.flush()
    return offer


def change_delivery_status(db: Session,order_id: int,user: User,expected_status: str,next_status: str ):
    try:
        partner = get_partner(db, user)

        order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())

        if not order:
            raise HTTPException(404, "Order not found")

        if order.delivery_partner_id != partner.id:
            raise HTTPException(403, "Not your delivery")

        if order.status != expected_status:
            raise HTTPException(409,f"Order must be {expected_status}")

        order.status = next_status

        db.add(OrderStatusHistory(order_id=order.id,old_status=expected_status,new_status=next_status,changed_by=f"delivery_partner:{partner.id}"))

        db.commit()
        return {"order_id": order.id, "status": next_status}

    except Exception:
        db.rollback()
        raise


def calculate_earnings(order: Order):
    amount = ( Decimal("25")+ Decimal("6") * Decimal(str(order.distance_km))+ Decimal(str(order.tip_amount)))
    return amount.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
