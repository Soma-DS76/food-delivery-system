
from fastapi import ( APIRouter,Depends,HTTPException)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_roles
from app.models.entities import (User,Cart,Coupon)
from app.schemas.cart import CartResponse
from app.schemas.coupon import ApplyCouponRequest
from app.routers.cart import build_cart_response
from app.services.coupons import (validate_coupon,money)

router = APIRouter(tags=["Cart Coupons"])


def get_locked_cart(db, customer_id):
    cart = db.scalar( select(Cart).where(Cart.customer_id == customer_id).with_for_update())

    if cart is None:
        raise HTTPException( status_code=400,detail="Your cart is empty")

    return cart


@router.post("/cart/apply-coupon", response_model=CartResponse)
def apply_coupon(data: ApplyCouponRequest,db: Session = Depends(get_db),customer: User = Depends(require_roles("customer"))):
    cart = get_locked_cart(db, customer.id)

    if cart.restaurant_id is None:
        raise HTTPException(status_code=400, detail="Add food items before applying a coupon")

    coupon = db.scalar( select(Coupon).where(Coupon.code == data.code.strip().upper()))

    if coupon is None:
        raise HTTPException(status_code=400, detail="Invalid coupon code")

    # Calculate subtotal without the old coupon.
    old_coupon_id = cart.coupon_id
    cart.coupon_id = None

    try:
        cart_data = build_cart_response(db, cart)

        if not cart_data["items"]:
            raise HTTPException(status_code=400,detail="Cart is empty")

        if not all( item["is_available"] for item in cart_data["items"]):
            raise HTTPException( status_code=400, detail="Cart contains unavailable items")

        subtotal = money(cart_data["item_total"])

        validate_coupon( db=db,coupon=coupon,customer_id=customer.id,restaurant_id=cart.restaurant_id,subtotal=subtotal)

    except Exception:
        cart.coupon_id = old_coupon_id
        raise

    cart.coupon_id = coupon.id
    db.commit()

    return build_cart_response( db, cart, customer_id=customer.id)


@router.delete("/cart/coupon", response_model=CartResponse)
def remove_coupon( db: Session = Depends(get_db), customer: User = Depends(require_roles("customer"))):
    cart = get_locked_cart(db, customer.id)

    cart.coupon_id = None
    db.commit()

    return build_cart_response( db, cart, customer_id=customer.id )
