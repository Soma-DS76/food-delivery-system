
from datetime import date, datetime, time
from fastapi import (APIRouter,Depends,HTTPException,Query)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.auth.security import get_current_user, require_roles
from app.models.entities import (User,Order,OrderStatusHistory,Coupon,CouponUsage,Payment,CartItem,MenuItem)
from app.schemas.order import (CheckoutRequest,OrderResponse,OrderSummaryResponse,OrderStatusHistoryResponse)
from app.services.checkout import checkout_order
from app.routers.cart import get_or_create_cart, build_cart_response


router = APIRouter(prefix="/orders",tags=["Orders & Checkout"])


def get_customer_order(db: Session,order_id: int,customer_id: int):
    order = db.scalar(select(Order).options(selectinload(Order.items)).where(Order.id == order_id,Order.customer_id == customer_id))

    if order is None:
        raise HTTPException(status_code=404,detail="Order not found")

    return order


@router.post("",response_model=OrderResponse,status_code=201)
def checkout(data: CheckoutRequest,db: Session = Depends(get_db),customer: User = Depends(require_roles("customer"))):
  
    order_id = checkout_order(db=db,customer_id=customer.id,address_id=data.address_id,payment_method=data.payment_method,tip_amount=data.tip_amount)

    return get_customer_order(db, order_id, customer.id)


@router.get("",response_model=list[OrderSummaryResponse])
def list_my_orders(limit: int = Query(default=20, ge=1, le=100),skip: int = Query(default=0, ge=0),
                   status: str | None = None, restaurant_id: int | None = Query(default=None, gt=0),
                   from_date: date | None = None, to_date: date | None = None,
                   db: Session = Depends(get_db),viewer: User = Depends(get_current_user)):
    role = getattr(viewer.role, "value", viewer.role)
    if role not in {"customer", "admin"}:
        raise HTTPException(status_code=403, detail="You do not have permission")
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date")

    statement = select(Order)
    if role == "customer":
        statement = statement.where(Order.customer_id == viewer.id)
    if status is not None:
        statement = statement.where(Order.status == status)
    if restaurant_id is not None:
        statement = statement.where(Order.restaurant_id == restaurant_id)
    if from_date is not None:
        statement = statement.where(Order.placed_at >= datetime.combine(from_date, time.min))
    if to_date is not None:
        statement = statement.where(Order.placed_at < datetime.combine(to_date, time.max))

    orders = db.scalars(statement.order_by(Order.placed_at.desc(),Order.id.desc())
        .offset(skip).limit(limit)).all()

    return orders


@router.get("/{order_id}",response_model=OrderResponse)
def get_order_details(order_id: int,db: Session = Depends(get_db),
                      viewer: User = Depends(get_current_user)):
    role = getattr(viewer.role, "value", viewer.role)
    if role == "customer":
        return get_customer_order(db, order_id, viewer.id)
    if role != "admin":
        raise HTTPException(status_code=403, detail="You do not have permission")
    order = db.scalar(select(Order).options(selectinload(Order.items)).where(Order.id == order_id))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/{order_id}/status-history",response_model=list[OrderStatusHistoryResponse])
def get_order_status_history(order_id: int,db: Session = Depends(get_db),customer: User = Depends(require_roles("customer"))):
    get_customer_order(db, order_id, customer.id)

    return db.scalars( select(OrderStatusHistory).where(OrderStatusHistory.order_id == order_id)
                      .order_by( OrderStatusHistory.changed_at,OrderStatusHistory.id)).all()


@router.put("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: int, db: Session = Depends(get_db),
                 customer: User = Depends(require_roles("customer"))):
    order = db.scalar(select(Order).where(
        Order.id == order_id, Order.customer_id == customer.id).with_for_update())
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "Placed":
        raise HTTPException(status_code=409, detail="Only orders that have not been accepted can be cancelled")

    old_status = order.status
    order.status = "Cancelled"
    if order.payment_method == "ONLINE" and order.payment_status == "Paid":
        order.payment_status = "Refunded"
        payment = db.scalar(select(Payment).where(Payment.order_id == order.id).with_for_update())
        if payment is not None:
            payment.status = "Refunded"

    if order.coupon_code:
        coupon = db.scalar(select(Coupon).where(Coupon.code == order.coupon_code))
        if coupon is not None:
            usage = db.scalar(select(CouponUsage).where(
                CouponUsage.order_id == order.id,
                CouponUsage.coupon_id == coupon.id).with_for_update())
            if usage is not None:
                db.delete(usage)

    db.add(OrderStatusHistory(order_id=order.id, old_status=old_status,
                              new_status="Cancelled", changed_by=f"customer:{customer.id}"))
    db.commit()
    return get_customer_order(db, order_id, customer.id)


@router.post("/{order_id}/reorder")
def reorder(order_id: int, db: Session = Depends(get_db),
            customer: User = Depends(require_roles("customer"))):
    previous_order = db.scalar(select(Order).options(selectinload(Order.items)).where(
        Order.id == order_id, Order.customer_id == customer.id))
    if previous_order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    cart = get_or_create_cart(db, customer.id)
    if cart.restaurant_id not in (None, previous_order.restaurant_id):
        raise HTTPException(status_code=409, detail="Your cart has items from another restaurant. Clear the cart to continue")

    cart.restaurant_id = previous_order.restaurant_id
    for old_item in previous_order.items:
        menu_item = db.get(MenuItem, old_item.menu_item_id)
        if menu_item is None or menu_item.is_deleted or not menu_item.is_available:
            continue

        existing = db.scalar(select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.menu_item_id == old_item.menu_item_id))
        if existing is not None:
            existing.quantity = min(10, existing.quantity + old_item.quantity)
        else:
            db.add(CartItem(cart_id=cart.id, menu_item_id=old_item.menu_item_id,
                            quantity=min(10, old_item.quantity)))

    db.commit()
    return build_cart_response(db, cart, customer_id=customer.id)
