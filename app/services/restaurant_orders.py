
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (User,Restaurant,Order,OrderStatusHistory,CouponUsage)
from app.services.delivery import assign_next_partner
from app.services.notifications import notify_order_status


# Restaurant-side transitions only.
ALLOWED_TRANSITIONS = { "Placed": {"Accepted", "Rejected"},"Accepted": {"Preparing"},
                        "Preparing": {"ReadyForPickup"},"ReadyForPickup": set(),"Rejected": set()}


def validate_transition(current_status: str,new_status: str):
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if new_status not in allowed:
        raise HTTPException(status_code=409,detail=(f"Cannot change order status from "f"{current_status} to {new_status}"))


def get_owned_restaurant_ids(db: Session,owner_id: int):
    return db.scalars(select(Restaurant.id).where(Restaurant.owner_id == owner_id,Restaurant.is_active.is_(True))).all()


def check_owner_approval(owner: User):
    if not owner.is_active or not owner.is_approved:
        raise HTTPException(status_code=403,detail="Restaurant owner is not approved")


def get_owned_order(db: Session,order_id: int,owner_id: int,lock: bool = False):
    statement = (select(Order).join(Restaurant,Order.restaurant_id == Restaurant.id)
        .where(Order.id == order_id,Restaurant.owner_id == owner_id,Restaurant.is_active.is_(True)))

    if lock:
        # Lock only the order row on MySQL.
        statement = statement.with_for_update(of=Order)

    order = db.scalar(statement)

    if order is None:
        raise HTTPException(status_code=404,detail="Order not found")

    return order


def change_order_status(db: Session,order_id: int,owner: User,new_status: str,reason: str | None = None):
   
    try:
        check_owner_approval(owner)

        order = get_owned_order(db=db,order_id=order_id,owner_id=owner.id,lock=True)

        old_status = order.status

        validate_transition(old_status, new_status)

        if new_status == "Rejected":
            if not reason or len(reason.strip()) < 5:
                raise HTTPException(status_code=422,detail="A rejection reason is required")

            # For the mock online gateway, rejecting a paid order marks it
            # refunded locally. A real gateway integration must issue an API refund.
            if order.payment_method == "ONLINE" and order.payment_status == "Paid":
                order.payment_status = "Refunded"
                from app.models.entities import Payment
                payment = db.scalar(select(Payment).where(Payment.order_id == order.id).with_for_update())
                if payment is not None:
                    payment.status = "Refunded"

            # Release the coupon redemption when the
            # restaurant rejects an unfulfilled COD order.
            # Lock the coupon first, preserving the
            # checkout coupon-usage serialization rule.
            if order.coupon_code:
                from app.models.entities import Coupon

                coupon = db.scalar( select(Coupon)
                    .where(Coupon.code == order.coupon_code)
                    .with_for_update())

                if coupon is not None:
                    usage = db.scalar(select(CouponUsage)
                        .where(CouponUsage.order_id == order.id,CouponUsage.coupon_id == coupon.id).with_for_update())

                    if usage is not None:
                        db.delete(usage)

        order.status = new_status

        # Existing Level 1 history model has no reason
        # column. Reason is not persisted in this version.
        history = OrderStatusHistory( order_id=order.id, old_status=old_status, new_status=new_status,
                                     changed_by=f"restaurant_owner:{owner.id}",reason=( reason.strip()
                                                                                       if new_status == "Rejected" 
                                                                                       else None ))
        db.add(history)

        db.commit()

        return order.id

    except Exception:
        db.rollback()
        raise
