
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_roles
from app.models.entities import (User,Cart,CartItem,MenuItem,Restaurant,Coupon )
from app.schemas.cart import ( AddCartItemRequest, UpdateCartItemRequest, CartResponse )
from app.services.coupons import validate_coupon

router = APIRouter( prefix="/cart", tags=["Shopping Cart"] )

ZERO = Decimal("0.00")
CENT = Decimal("0.01")

DIFFERENT_RESTAURANT_MESSAGE = ( "Your cart has items from another restaurant. " "Clear the cart to continue" )


def money(value):
    return Decimal(str(value)).quantize(CENT)


def calculate_line_total(price, quantity):
    return money(price) * quantity


def get_cart(db: Session, customer_id: int):
    return db.scalar( select(Cart) .where(Cart.customer_id == customer_id) .with_for_update() )


def get_or_create_cart(db: Session, customer_id: int):
    # Lock the user row to serialize first-cart creation.
    db.execute( select(User.id).where(User.id == customer_id).with_for_update()).first()

    cart = get_cart(db, customer_id)

    if cart is None:
        cart = Cart( customer_id=customer_id, restaurant_id=None, coupon_id=None )
        db.add(cart)
        db.flush()

    return cart


def get_valid_menu_item(db: Session, menu_item_id: int):
    item = db.get(MenuItem, menu_item_id)

    if ( item is None or item.is_deleted or not item.is_available ):
        raise HTTPException( status_code=400, detail="Menu item is unavailable" )

    restaurant = db.get(Restaurant, item.restaurant_id)

    if ( restaurant is None or not restaurant.is_active or restaurant.is_temporarily_closed ):
        raise HTTPException( status_code=400, detail="Restaurant is not accepting orders")

    return item


def get_customer_cart_item(db: Session,cart: Cart, item_id: int ):

    item = db.scalar(
        select(CartItem).where( CartItem.id == item_id, CartItem.cart_id == cart.id ))

    if item is None:
        raise HTTPException( status_code=404, detail="Cart item not found" )

    return item


def reset_empty_cart(db: Session, cart: Cart):
    remaining = db.scalar( select(CartItem.id) .where(CartItem.cart_id == cart.id) .limit(1) )

    if remaining is None:
        cart.restaurant_id = None
        cart.coupon_id = None


def build_cart_response(db: Session,cart: Cart | None, customer_id: int | None = None):

    if cart is None:
        return {    "cart_id": None,
                    "restaurant_id": None,
                    "restaurant_name": None,
                    "items": [],
                    "item_total": ZERO,
                    "packaging_total": ZERO,
                    "coupon_code": None,
                    "discount_amount": ZERO,
                    "item_total_after_discount": ZERO,
                    "grand_total": ZERO }

    cart_items = db.scalars( select(CartItem) .where(CartItem.cart_id == cart.id).order_by(CartItem.id)).all()

    restaurant = ( db.get(Restaurant, cart.restaurant_id) if cart.restaurant_id is not None else None )

    items = []
    item_total = ZERO
    packaging_total = ZERO

    for cart_item in cart_items:
        menu_item = db.get( MenuItem, cart_item.menu_item_id )

        if menu_item is None:
            raise HTTPException( status_code=409, detail="Cart contains an invalid menu item" )

        price = money(menu_item.price)
        packaging = money(menu_item.packaging_charge)
        quantity = cart_item.quantity

        line_total = calculate_line_total( price, quantity )

        item_total += line_total
        packaging_total += packaging * quantity

        restaurant_active = ( restaurant is not None and restaurant.is_active and not restaurant.is_temporarily_closed )

        items.append({  "id": cart_item.id,
                        "menu_item_id": menu_item.id,
                        "name": menu_item.name,
                        "quantity": quantity,
                        "unit_price": price,
                        "packaging_charge": packaging,
                        "line_total": line_total,
                        "is_available": ( menu_item.is_available and not menu_item.is_deleted and restaurant_active )})

    coupon_code = None

    if cart.coupon_id is not None:
        coupon = db.get(Coupon, cart.coupon_id)
        if coupon is not None:
            coupon_code = coupon.code

    # Coupon calculation is implemented in Level 6.
    discount_amount = ZERO

    if cart.coupon_id is not None:
        coupon = db.get(Coupon, cart.coupon_id)

        if coupon is None:
            raise HTTPException( status_code=409, detail="Applied coupon no longer exists" )

        if customer_id is None:
            customer_id = cart.customer_id

        # Revalidate whenever the cart is displayed.
        # Invalid coupons are rejected, not silently used.
        discount_amount = validate_coupon( db=db,coupon=coupon,customer_id=customer_id,
                                           restaurant_id=cart.restaurant_id,subtotal=item_total )


    item_total_after_discount = money( item_total - discount_amount )

    grand_total = money(item_total_after_discount + packaging_total )

    return {"cart_id": cart.id,
            "restaurant_id": cart.restaurant_id,
            "restaurant_name": ( restaurant.name if restaurant else None),
            "items": items,
            "item_total": money(item_total),
            "packaging_total": money(packaging_total),
            "coupon_code": coupon_code,
            "discount_amount": discount_amount,
            "item_total_after_discount": item_total_after_discount,
            "grand_total": grand_total }


# -----------------------------------
# GET CART
# -----------------------------------

@router.get("", response_model=CartResponse)
def view_cart(db: Session = Depends(get_db),customer: User = Depends(require_roles("customer"))):
    cart = db.scalar( select(Cart).where( Cart.customer_id == customer.id ))

    return build_cart_response(db, cart)


# -----------------------------------
# ADD ITEM TO CART
# -----------------------------------

@router.post("/items", response_model=CartResponse)
def add_item( data: AddCartItemRequest, db: Session = Depends(get_db), 
              customer: User = Depends(require_roles("customer"))):
    cart = get_or_create_cart(db, customer.id)

    menu_item = get_valid_menu_item( db, data.menu_item_id )

    if ( cart.restaurant_id is not None and cart.restaurant_id != menu_item.restaurant_id ):
        raise HTTPException( status_code=409,detail=DIFFERENT_RESTAURANT_MESSAGE )

    existing_item = db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id,CartItem.menu_item_id == menu_item.id))

    if existing_item:
        new_quantity = (existing_item.quantity + data.quantity)

        if new_quantity > 10:
            raise HTTPException( status_code=422,detail="Maximum quantity is 10 per item")

        existing_item.quantity = new_quantity

    else:
        cart_item = CartItem( cart_id=cart.id,menu_item_id=menu_item.id,quantity=data.quantity)

        db.add(cart_item)

    cart.restaurant_id = menu_item.restaurant_id

    db.commit()

    return build_cart_response(db, cart)


# -----------------------------------
# UPDATE ITEM QUANTITY
# -----------------------------------

@router.put( "/items/{item_id}",response_model=CartResponse)
def update_item( item_id: int,data: UpdateCartItemRequest,db: Session = Depends(get_db),
                 customer: User = Depends(require_roles("customer"))):
   
    cart = get_cart(db, customer.id)

    if cart is None:
        raise HTTPException( status_code=404, detail="Cart not found" )

    cart_item = get_customer_cart_item( db, cart, item_id )

    get_valid_menu_item( db, cart_item.menu_item_id )

    cart_item.quantity = data.quantity

    db.commit()

    return build_cart_response(db, cart)


# -----------------------------------
# REMOVE ITEM
# -----------------------------------

@router.delete( "/items/{item_id}",response_model=CartResponse)
def remove_item( item_id: int, db: Session = Depends(get_db),customer: User = Depends(require_roles("customer"))):

    cart = get_cart(db, customer.id)

    if cart is None:
        raise HTTPException( status_code=404, detail="Cart not found" ) 
    
    cart_item = get_customer_cart_item( db, cart, item_id )

    db.delete(cart_item)
    db.flush()

    reset_empty_cart(db, cart)

    db.commit()

    return build_cart_response(db, cart)


# -----------------------------------
# CLEAR ENTIRE CART
# -----------------------------------

@router.delete("")
def clear_cart( db: Session = Depends(get_db), customer: User = Depends(require_roles("customer"))):
    cart = get_cart(db, customer.id)

    if cart is None:
        return { "message": "Cart is already empty" }

    items = db.scalars( select(CartItem).where( CartItem.cart_id == cart.id )).all()

    for item in items:
        db.delete(item)

    cart.restaurant_id = None
    cart.coupon_id = None

    db.commit()

    return { "message": "Cart cleared successfully" }
