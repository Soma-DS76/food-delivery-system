
from decimal import Decimal
from fastapi import (APIRouter,Depends,HTTPException,Query)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_roles
from app.models.entities import (User,Coupon,Restaurant,Cart,CartItem,MenuItem)
from app.schemas.coupon import (CouponCreate,CouponUpdate,CouponResponse)
from app.services.coupons import validate_coupon

router = APIRouter( prefix="/coupons",tags=["Coupon Management"])


def find_coupon(db, coupon_id):
    coupon = db.get(Coupon, coupon_id)

    if coupon is None:
        raise HTTPException(status_code=404,detail="Coupon not found")

    return coupon


@router.post("",response_model=CouponResponse,status_code=201)
def create_coupon(data: CouponCreate,db: Session = Depends(get_db),
                  creator: User = Depends(require_roles("admin", "restaurant_owner"))):
    code = data.code.strip().upper()

    existing = db.scalar(select(Coupon).where(Coupon.code == code))

    if existing:
        raise HTTPException( status_code=409, detail="Coupon code already exists" )

    role = getattr(creator.role, "value", creator.role)
    if role == "admin":
        if data.restaurant_id is not None and db.get(Restaurant, data.restaurant_id) is None:
            raise HTTPException(status_code=404,detail="Restaurant not found")
    else:
        if not creator.is_approved:
            raise HTTPException(status_code=403, detail="Admin approval required")
        if data.restaurant_id is None:
            raise HTTPException(status_code=403, detail="Restaurant owners can create only restaurant coupons")
        restaurant = db.get(Restaurant, data.restaurant_id)
        if restaurant is None:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        if restaurant.owner_id != creator.id:
            raise HTTPException(status_code=403, detail="You cannot manage coupons for this restaurant")

    coupon = Coupon(**data.model_dump(exclude={"code"}),code=code,created_by=creator.id)

    db.add(coupon)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409,detail="Coupon code already exists")

    db.refresh(coupon)
    return coupon


@router.get("",response_model=list[CouponResponse])
def list_coupons(restaurant_id: int | None = Query(default=None, gt=0),
                 is_active: bool | None = None, discount_type: str | None = None,
                 skip: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
                 db: Session = Depends(get_db),
                 viewer: User = Depends(require_roles("admin", "restaurant_owner"))):
    statement = select(Coupon)
    role = getattr(viewer.role, "value", viewer.role)
    if role == "restaurant_owner":
        statement = statement.join(Restaurant, Coupon.restaurant_id == Restaurant.id).where(
            Restaurant.owner_id == viewer.id)
    if restaurant_id is not None:
        statement = statement.where(Coupon.restaurant_id == restaurant_id)
    if is_active is not None:
        statement = statement.where(Coupon.is_active.is_(is_active))
    if discount_type is not None:
        if discount_type not in {"percentage", "flat"}:
            raise HTTPException(status_code=422, detail="discount_type must be percentage or flat")
        statement = statement.where(Coupon.discount_type == discount_type)
    return db.scalars(statement.order_by(Coupon.id.desc()).offset(skip).limit(limit)).all()


@router.get("/available")
def available_coupons(db: Session = Depends(get_db),
                      customer: User = Depends(require_roles("customer"))):
    cart = db.scalar(select(Cart).where(Cart.customer_id == customer.id))
    if cart is None or cart.restaurant_id is None:
        return []

    cart_items = db.scalars(select(CartItem).where(CartItem.cart_id == cart.id)).all()
    subtotal = Decimal("0.00")
    for cart_item in cart_items:
        item = db.get(MenuItem, cart_item.menu_item_id)
        if item is None or item.is_deleted or not item.is_available:
            return []
        subtotal += Decimal(str(item.price)) * cart_item.quantity

    statement = select(Coupon).where(
        Coupon.is_active.is_(True),
        (Coupon.restaurant_id.is_(None) | (Coupon.restaurant_id == cart.restaurant_id)))
    coupons = db.scalars(statement.order_by(Coupon.code)).all()
    available = []
    for coupon in coupons:
        try:
            discount = validate_coupon(db, coupon, customer.id, cart.restaurant_id, subtotal)
        except HTTPException:
            continue
        available.append({"coupon": CouponResponse.model_validate(coupon),
                          "discount_amount": discount})
    return available


@router.put( "/{coupon_id}",response_model=CouponResponse )
def update_coupon( coupon_id: int,data: CouponUpdate,db: Session = Depends(get_db),
                   admin: User = Depends(require_roles("admin", "restaurant_owner"))):
    
    coupon = find_coupon(db, coupon_id)
    role = getattr(admin.role, "value", admin.role)
    if role == "restaurant_owner":
        restaurant = db.get(Restaurant, coupon.restaurant_id) if coupon.restaurant_id else None
        if restaurant is None or restaurant.owner_id != admin.id:
            raise HTTPException(status_code=403, detail="You cannot manage this coupon")

    changes = data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if field != "description" and value is None:
            raise HTTPException( status_code=422,detail=f"{field} cannot be null")

    if ("valid_to" in changes and changes["valid_to"] <= coupon.valid_from):
        raise HTTPException( status_code=422,detail="valid_to must be after valid_from")

    for field, value in changes.items():
        setattr(coupon, field, value)

    db.commit()
    db.refresh(coupon)

    return coupon


@router.put("/{coupon_id}/deactivate")
def deactivate_coupon(coupon_id: int,db: Session = Depends(get_db),
                      admin: User = Depends(require_roles("admin", "restaurant_owner"))):
    coupon = find_coupon(db, coupon_id)
    role = getattr(admin.role, "value", admin.role)
    if role == "restaurant_owner":
        restaurant = db.get(Restaurant, coupon.restaurant_id) if coupon.restaurant_id else None
        if restaurant is None or restaurant.owner_id != admin.id:
            raise HTTPException(status_code=403, detail="You cannot manage this coupon")
    coupon.is_active = False

    db.commit()

    return { "message": "Coupon deactivated successfully" }
