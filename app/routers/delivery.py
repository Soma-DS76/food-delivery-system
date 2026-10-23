
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_roles
from app.models.entities import (User, Order, DeliveryPartner, DeliveryOffer,OrderStatusHistory)
from app.schemas.delivery import (AvailabilityUpdate, LocationUpdate, DeliveryOTP,OfferResponse, EarningsResponse)
from app.services.delivery import (get_partner, has_active_delivery, now_utc,assign_next_partner, change_delivery_status,calculate_earnings)
from sqlalchemy import select
from app.services.tracking import tracking_manager


router = APIRouter(tags=["Delivery Partner"])



def partner_dependency(user: User = Depends(require_roles("delivery_partner"))):
    return user



@router.put("/partners/me/availability")
def update_availability(data: AvailabilityUpdate,db: Session = Depends(get_db),user: User = Depends(partner_dependency),):
    partner = get_partner(db, user)

    if data.is_online and has_active_delivery(db, partner.id):
        raise HTTPException(409, "You already have an active delivery")

    partner.is_online = data.is_online
    db.commit()

    return {"is_online": partner.is_online}



@router.put("/partners/me/location")
async def update_location( data: LocationUpdate,db: Session = Depends(get_db),user: User = Depends(partner_dependency)):
    
    partner = get_partner(db, user)
    partner.current_latitude = data.latitude
    partner.current_longitude = data.longitude
    partner.last_location_at = now_utc()

    db.commit()

    active_orders = db.scalars(
        select(Order).where(Order.delivery_partner_id == partner.id,
            Order.status.in_(["Accepted","Preparing","ReadyForPickup","PickedUp","OutForDelivery"]))).all()

    for order in active_orders:
        await tracking_manager.broadcast(
            order.id,{  "type": "location_update","order_id": order.id,"latitude": data.latitude,
                "longitude": data.longitude,"updated_at": partner.last_location_at.isoformat()})

    return {"message": "Location updated and broadcast"}



@router.get("/partners/me/offers")
def my_offers( db: Session = Depends(get_db),user: User = Depends(partner_dependency)):
    partner = get_partner(db, user)

    offers = db.scalars( select(DeliveryOffer).where(DeliveryOffer.partner_id == partner.id).order_by(DeliveryOffer.offered_at.desc())).all()

    return [
        {
            "id": offer.id,
            "order_id": offer.order_id,
            "status": (
                "Expired"
                if offer.status == "Pending"
                and offer.expires_at <= now_utc()
                else offer.status
            ),
            "offered_at": offer.offered_at,
            "expires_at": offer.expires_at,
        }
        for offer in offers
    ]


@router.put("/offers/{offer_id}/accept")
def accept_offer(offer_id: int,db: Session = Depends(get_db), user: User = Depends(partner_dependency)):
    try:
        partner = get_partner(db, user)

        # Read offer ID first, then lock the order.
        offer_info = db.get(DeliveryOffer, offer_id)

        if not offer_info:
            raise HTTPException(404, "Offer not found")

        order = db.scalar(select(Order).where(Order.id == offer_info.order_id).with_for_update())

        # Lock partner to prevent simultaneous assignments.
        partner = db.scalar( select(DeliveryPartner).where(DeliveryPartner.id == partner.id).with_for_update())

        offer = db.scalar(select(DeliveryOffer).where(DeliveryOffer.id == offer_id).with_for_update())

        if offer.partner_id != partner.id:
            raise HTTPException(403, "Not your offer")

        if offer.status != "Pending":
            raise HTTPException(409, "Offer is not pending")

        if offer.expires_at <= now_utc():
            offer.status = "Expired"
            db.commit()
            raise HTTPException(409, "Offer expired")

        if not partner.is_online:
            raise HTTPException(409, "Partner is offline")

        if has_active_delivery(db, partner.id):
            raise HTTPException(409, "Active delivery exists")

        if order.delivery_partner_id is not None:
            raise HTTPException(409, "Order already assigned")

        if order.status not in ("Accepted", "Preparing", "ReadyForPickup"):
            raise HTTPException(409, "Order cannot be assigned")

        order.delivery_partner_id = partner.id
        offer.status = "Accepted"

        db.commit()

        return { "message": "Delivery accepted","order_id": order.id}

    except Exception:
        db.rollback()
        raise


@router.put("/offers/{offer_id}/decline")
def decline_offer(offer_id: int,db: Session = Depends(get_db),user: User = Depends(partner_dependency)):

    try:
        partner = get_partner(db, user)
        initial = db.get(DeliveryOffer, offer_id)

        if not initial:
            raise HTTPException(404, "Offer not found")

        order = db.scalar(select(Order).where(Order.id == initial.order_id).with_for_update())

        offer = db.scalar(select(DeliveryOffer).where(DeliveryOffer.id == offer_id).with_for_update())

        if offer.partner_id != partner.id:
            raise HTTPException(403, "Not your offer")

        if offer.status != "Pending":
            raise HTTPException(409, "Offer not pending")

        offer.status = "Declined"

        next_offer = assign_next_partner(db, order.id)
        db.commit()

        return {"message": "Offer declined", "next_offer_id": (next_offer.id if next_offer else None)}

    except Exception:
        db.rollback()
        raise


@router.put("/orders/{order_id}/pickup")
def pickup(order_id: int,db: Session = Depends(get_db),user: User = Depends(partner_dependency)):
    return change_delivery_status(db, order_id, user,"ReadyForPickup", "PickedUp")


@router.put("/orders/{order_id}/out-for-delivery")
def out_for_delivery(order_id: int,db: Session = Depends(get_db),user: User = Depends(partner_dependency)):
    return change_delivery_status(db, order_id, user,"PickedUp", "OutForDelivery"  )



@router.put("/orders/{order_id}/deliver")
def deliver( order_id: int,data: DeliveryOTP,db: Session = Depends(get_db),user: User = Depends(partner_dependency),):
    try:
        partner = get_partner(db, user)

        order = db.scalar( select(Order).where(Order.id == order_id).with_for_update())

        if order is None:
            raise HTTPException(404, "Order not found")

        if order.delivery_partner_id != partner.id:
            raise HTTPException(403, "Not your delivery")

        if order.status != "OutForDelivery":
            raise HTTPException( 409, "Order is not out for delivery" )

        if order.otp_locked:
            raise HTTPException( 403, "OTP locked. Contact admin" )

        if data.otp != order.delivery_otp:
            order.otp_failed_attempts += 1

            if order.otp_failed_attempts >= 3:
                order.otp_locked = True

            locked = order.otp_locked
            db.commit()

            raise HTTPException( 403 if locked else 400, "OTP locked after 3 failed attempts" if locked else "Invalid OTP")

        order.status = "Delivered"
        order.delivered_at = now_utc()

        if order.payment_method == "COD":
            order.payment_status = "Paid"

        db.add(OrderStatusHistory( order_id=order.id,old_status="OutForDelivery",new_status="Delivered",changed_by=f"delivery_partner:{partner.id}"))

        db.commit()

        return { "message": "Order delivered successfully",
                "order_id": order.id,"payment_status": order.payment_status}

    except HTTPException:
        # A committed OTP failure remains saved.
        # Other errors roll back pending changes.
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise



@router.get("/partners/me/earnings")
def earnings(from_date: date | None = None,to_date: date | None = None,db: Session = Depends(get_db),user: User = Depends(partner_dependency)):
    partner = get_partner(db, user)

    today = date.today()
    start = from_date or today
    end = to_date or today

    if start > end:
        raise HTTPException(422, "from_date must not exceed to_date")

    orders = db.scalars(
        select(Order).where(Order.delivery_partner_id == partner.id,
                            Order.status == "Delivered",
                            Order.delivered_at >= datetime.combine(start, time.min),
                            Order.delivered_at < datetime.combine(end + timedelta(days=1), time.min))).all()

    total = sum((calculate_earnings(order) for order in orders),Decimal("0.00"))

    return { "from_date": start,"to_date": end,"delivery_count": len(orders),"total_earnings": total}
