
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.entities import ( Coupon,CouponUsage,Order )


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value):
    return Decimal(str(value)).quantize(CENT,rounding=ROUND_HALF_UP)


def calculate_discount(coupon, subtotal):
    subtotal = money(subtotal)

    if coupon.discount_type == "percentage":
        discount = (subtotal * Decimal(str(coupon.discount_value))/ Decimal("100"))
    elif coupon.discount_type == "flat":
        discount = Decimal(str(coupon.discount_value))
    else:
        raise HTTPException(status_code=400,detail="Unsupported discount type" )

    discount = money(discount)

    if coupon.max_discount is not None:
        discount = min( discount, money(coupon.max_discount) )

    return min(discount, subtotal)


def validate_coupon(db: Session,coupon: Coupon,customer_id: int,restaurant_id: int,subtotal: Decimal):

    now = datetime.now(timezone.utc).replace( tzinfo=None )

    if not coupon.is_active:
        raise HTTPException( status_code=400, detail="Coupon is inactive")

    if not ( coupon.valid_from <= now < coupon.valid_to ):
        raise HTTPException(status_code=400,detail="Coupon is not currently valid")

    if ( coupon.restaurant_id is not None and coupon.restaurant_id != restaurant_id ):
        raise HTTPException( status_code=400, detail="Coupon is not valid for this restaurant" )

    if money(subtotal) < money(coupon.min_order_value):
        raise HTTPException(
            status_code=400,
            detail=("Minimum order value is "f"{coupon.min_order_value}"))

    total_used = db.scalar( select(func.count(CouponUsage.id)) .where(CouponUsage.coupon_id == coupon.id)) or 0

    if ( coupon.total_usage_limit is not None and total_used >= coupon.total_usage_limit ):
        raise HTTPException( status_code=400,detail="Coupon usage limit reached" )

    user_used = db.scalar( select(func.count(CouponUsage.id))
                           .where(CouponUsage.coupon_id == coupon.id,CouponUsage.customer_id == customer_id)) or 0

    if ( coupon.per_user_limit is not None and user_used >= coupon.per_user_limit ):
        raise HTTPException( status_code=400, detail="Your coupon usage limit is reached" )

    if coupon.first_order_only:
        previous_orders = db.scalar(
            select(func.count(Order.id)).where(
                Order.customer_id == customer_id,
                Order.status == "Delivered",
            )
        ) or 0

        if previous_orders > 0:
            raise HTTPException(status_code=400, detail="This coupon is for customers with no previous delivered orders")

    return calculate_discount(coupon, subtotal)
