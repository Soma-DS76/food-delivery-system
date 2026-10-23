
from fastapi import (APIRouter,Depends,Query,HTTPException)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.auth.security import require_roles
from app.models.entities import (User,Order,Restaurant,OrderStatusHistory)
from app.schemas.restaurant_order import (RejectOrderRequest,RestaurantOrderSummary,RestaurantOrderDetail,RestaurantOrderHistoryResponse)
from app.services.restaurant_orders import ( check_owner_approval,get_owned_order,change_order_status,ALLOWED_TRANSITIONS)


router = APIRouter(tags=["Restaurant Order Management"])


@router.get("/restaurants/me/orders", response_model=list[RestaurantOrderSummary])
def list_restaurant_orders( restaurant_id: int | None = Query(default=None, gt=0),status: str | None = Query(default=None),
                           limit: int = Query(default=20, ge=1, le=100),skip: int = Query(default=0, ge=0),
                           db: Session = Depends(get_db),owner: User = Depends(require_roles("restaurant_owner"))):
    check_owner_approval(owner)

    stmt = (select(Order).join(Restaurant,Order.restaurant_id == Restaurant.id).where(Restaurant.owner_id == owner.id,Restaurant.is_active.is_(True)) )

    if restaurant_id is not None:
        stmt = stmt.where( Restaurant.id == restaurant_id )

    if status is not None:
        valid_statuses = ( set(ALLOWED_TRANSITIONS) | {"PickedUp", "OnTheWay", "Delivered", "Cancelled"} )

        if status not in valid_statuses:
            raise HTTPException( status_code=422,detail="Invalid order status filter")

        stmt = stmt.where(Order.status == status)

    stmt = (stmt.order_by(Order.placed_at.desc(),Order.id.desc()).offset(skip).limit(limit))

    return db.scalars(stmt).all()


@router.get("/restaurants/me/orders/{order_id}",response_model=RestaurantOrderDetail)
def get_restaurant_order(order_id: int,db: Session = Depends(get_db),owner: User = Depends(require_roles("restaurant_owner"))):
    
    check_owner_approval(owner)
    order = get_owned_order(db, order_id, owner.id)

    return db.scalar(select(Order) .options(selectinload(Order.items)).where(Order.id == order.id))


@router.put("/orders/{order_id}/accept",response_model=RestaurantOrderDetail)
def accept_order( order_id: int,db: Session = Depends(get_db),owner: User = Depends(require_roles("restaurant_owner"))):
  
    updated_id = change_order_status(db, order_id, owner, "Accepted")

    return get_restaurant_order( updated_id, db, owner)


@router.put("/orders/{order_id}/reject",response_model=RestaurantOrderDetail)
def reject_order( order_id: int,data: RejectOrderRequest,db: Session = Depends(get_db),
                  owner: User = Depends(require_roles("restaurant_owner"))):
    updated_id = change_order_status(db=db, order_id=order_id,owner=owner,new_status="Rejected",reason=data.reason)

    return get_restaurant_order(updated_id, db, owner)


@router.put("/orders/{order_id}/preparing",response_model=RestaurantOrderDetail)
def start_preparing(order_id: int,db: Session = Depends(get_db),owner: User = Depends(require_roles("restaurant_owner"))):
    updated_id = change_order_status( db, order_id, owner, "Preparing")

    return get_restaurant_order(updated_id, db, owner)


@router.put("/orders/{order_id}/ready",response_model=RestaurantOrderDetail)
def mark_ready(order_id: int,db: Session = Depends(get_db),owner: User = Depends(require_roles("restaurant_owner"))):
    updated_id = change_order_status(db, order_id, owner, "ReadyForPickup")

    return get_restaurant_order(updated_id, db, owner)


@router.get("/restaurants/me/orders/{order_id}/history",response_model=list[RestaurantOrderHistoryResponse])
def restaurant_order_history( order_id: int, db: Session = Depends(get_db),owner: User = Depends( require_roles("restaurant_owner"))):
    check_owner_approval(owner)

    get_owned_order( db, order_id, owner.id )

    return db.scalars( select(OrderStatusHistory)
        .where( OrderStatusHistory.order_id == order_id )
        .order_by( OrderStatusHistory.changed_at, OrderStatusHistory.id ) ).all()
