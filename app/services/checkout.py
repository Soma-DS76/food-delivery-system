
import secrets
import uuid
from math import ceil
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import ( User,Address,Restaurant,MenuItem,Cart,
                                  CartItem,Coupon,CouponUsage,Order,OrderItem,OrderStatusHistory,Payment)
from app.utils.distance import haversine_distance
from app.services.coupons import validate_coupon


CENT = Decimal("0.01")
ZERO = Decimal("0.00")

PLATFORM_FEE = Decimal("5.00")


def money(value):
    return Decimal(str(value)).quantize(CENT,rounding=ROUND_HALF_UP)


def calculate_delivery_fee(distance_km: float) -> Decimal:
    extra_distance = max(0, ceil(distance_km - 3))
    return Decimal("20.00") + Decimal("8.00") * extra_distance


def calculate_order_total(item_total,discount,packaging,delivery_fee,platform_fee,gst,tip):
    values = [item_total,discount,packaging,delivery_fee,platform_fee,gst,tip]

    (item_total,discount,packaging,delivery_fee,platform_fee,gst,tip ) = [money(value) for value in values]

    if discount < ZERO or discount > item_total:
        raise ValueError("Invalid discount amount")

    if any( value < ZERO for value in ( item_total,packaging,delivery_fee,platform_fee,gst,tip)):
        raise ValueError("Amounts cannot be negative")

    return money(   item_total
                    - discount
                    + packaging
                    + delivery_fee
                    + platform_fee
                    + gst
                    + tip)


def create_order_number():
    return f"FD-{uuid.uuid4().hex[:20].upper()}"


def checkout_order(db: Session,customer_id: int,address_id: int,payment_method: str,tip_amount: Decimal):
    try:
        # Lock the customer row to serialize checkouts
        # for the same customer.
        customer = db.scalar(select(User).where(User.id == customer_id).with_for_update())

        if customer is None or not customer.is_active:
            raise HTTPException( status_code=403,detail="Customer account is inactive")

        cart = db.scalar(select(Cart).where(Cart.customer_id == customer_id).with_for_update())

        if cart is None or cart.restaurant_id is None:
            raise HTTPException( status_code=400,detail="Your cart is empty")

        address = db.scalar(select(Address).where(Address.id == address_id,Address.customer_id == customer_id).with_for_update())

        if address is None:
            raise HTTPException(status_code=404,detail="Delivery address not found")

        restaurant = db.scalar( select(Restaurant).where(Restaurant.id == cart.restaurant_id).with_for_update())

        if (restaurant is None or not restaurant.is_active or restaurant.is_temporarily_closed):
            raise HTTPException(status_code=400,detail="Restaurant is not accepting orders")

        # Level 3 opening-hours helper.
        from app.routers.restaurants import is_restaurant_open

        if not is_restaurant_open(restaurant):
            raise HTTPException(status_code=400,detail="Restaurant is currently closed")

        distance = haversine_distance(restaurant.latitude,restaurant.longitude,address.latitude,address.longitude)

        if distance > restaurant.delivery_radius_km:
            raise HTTPException(status_code=400,detail="Address is outside delivery radius")

        cart_items = db.scalars( select(CartItem).where(CartItem.cart_id == cart.id)
                                .order_by(CartItem.menu_item_id).with_for_update()).all()

        if not cart_items:
            raise HTTPException(status_code=400, detail="Your cart is empty")

        menu_ids = sorted( {item.menu_item_id for item in cart_items})

        # Lock menu rows while validating current prices
        # and availability.
        menu_items = db.scalars( select(MenuItem) .where(MenuItem.id.in_(menu_ids)) .order_by(MenuItem.id).with_for_update()).all()

        menu_map = { item.id: item for item in menu_items }

        item_total = ZERO
        packaging_total = ZERO
        order_items_data = []

        for cart_item in cart_items:
            menu_item = menu_map.get( cart_item.menu_item_id )

            if ( menu_item is None or menu_item.is_deleted or not menu_item.is_available or menu_item.restaurant_id != restaurant.id):
                raise HTTPException(status_code=400, detail=(f"Menu item {cart_item.menu_item_id} " "is unavailable" ))

            quantity = cart_item.quantity

            if not 1 <= quantity <= 10:
                raise HTTPException( status_code=400, detail="Invalid cart item quantity" )

            price = money(menu_item.price)
            packaging = money( menu_item.packaging_charge )

            if price < ZERO or packaging < ZERO:
                raise HTTPException( status_code=409, detail="Invalid menu pricing" )

            item_total += price * quantity
            packaging_total += packaging * quantity

            order_items_data.append({ "menu_item_id": menu_item.id,"item_name": menu_item.name,"quantity": quantity,
                                     "unit_price": price,"packaging_charge": packaging })

        item_total = money(item_total)
        packaging_total = money(packaging_total)

        if item_total < money(restaurant.min_order_value):
            raise HTTPException( status_code=400, detail=( "Restaurant minimum order value is " f"{restaurant.min_order_value}" ))

        coupon_code = None
        discount = ZERO
        coupon = None

        if cart.coupon_id is not None:
            # Lock the coupon row so concurrent checkouts
            # cannot both consume the last usage.
            coupon = db.scalar( select(Coupon) .where(Coupon.id == cart.coupon_id).with_for_update() )

            if coupon is None:
                raise HTTPException( status_code=400, detail="Applied coupon not found" )

            discount = validate_coupon( db=db, coupon=coupon, customer_id=customer_id,restaurant_id=restaurant.id,subtotal=item_total )

            coupon_code = coupon.code

        tip = money(tip_amount)
        delivery_fee = calculate_delivery_fee(distance)
        gst_amount = money((item_total - discount) * Decimal("0.05"))

        grand_total = calculate_order_total( item_total=item_total,discount=discount,
                                            packaging=packaging_total,delivery_fee=delivery_fee,
                                            platform_fee=PLATFORM_FEE,gst=gst_amount, tip=tip )

        payment_method = str(payment_method).upper()
        if payment_method not in {"COD", "ONLINE"}:
            raise HTTPException(status_code=422, detail="payment_method must be COD or ONLINE")

        # Generate OTP internally; never include it
        # in the customer-facing response.
        delivery_otp = f"{secrets.randbelow(10000):04d}"

        order = Order(  order_number=create_order_number(),
                        customer_id=customer_id,
                        restaurant_id=restaurant.id,
                        address_id=address.id,
                        item_total=item_total,
                        coupon_code=coupon_code,
                        discount_amount=discount,
                        packaging_charges=packaging_total,
                        delivery_fee=delivery_fee,
                        platform_fee=PLATFORM_FEE,
                        gst_amount=gst_amount,
                        tip_amount=tip,
                        grand_total=grand_total,
                        payment_method=payment_method,
                        payment_status=("Paid" if payment_method == "ONLINE" else "Pending"),
                        status="Placed",
                        distance_km=round(distance, 2),
                        delivery_otp=delivery_otp,
                        otp_failed_attempts=0,
                        otp_locked=False)

        db.add(order)
        db.flush()

        # Mock online payment: no external gateway is contacted. The order
        # and payment record are committed atomically in this transaction.
        if payment_method == "ONLINE":
            db.add(Payment(order_id=order.id, customer_id=customer_id,
                           amount=grand_total, payment_method="ONLINE",
                           provider="mock", status="Paid"))

        for item_data in order_items_data:
            db.add( OrderItem( order_id=order.id, **item_data ) )

        db.add( OrderStatusHistory( order_id=order.id, old_status=None, new_status="Placed",changed_by=f"customer:{customer_id}" ) )

        if coupon is not None:
            db.add(
                CouponUsage( coupon_id=coupon.id, customer_id=customer_id, order_id=order.id ))

        for cart_item in cart_items:
            db.delete(cart_item)

        cart.restaurant_id = None
        cart.coupon_id = None

        # Flush all changes before committing.
        db.flush()
        db.commit()

        return order.id

    except Exception:
        db.rollback()
        raise
