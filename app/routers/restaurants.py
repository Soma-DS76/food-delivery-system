
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import ( User, Restaurant,MenuCategory,MenuItem )
from app.auth.security import require_roles
from app.schemas.restaurant import (RestaurantCreate,RestaurantUpdate,RestaurantResponse,
                                    OpenStatusUpdate,CategoryCreate,CategoryResponse,
                                    MenuItemCreate,MenuItemUpdate,MenuItemResponse,
                                    AvailabilityUpdate,RestaurantMenuResponse)


from fastapi import Query
from app.utils.distance import (haversine_distance,estimated_delivery_minutes)


router = APIRouter(tags=["Restaurants & Menus"])

# Change this if your restaurants use another timezone.
RESTAURANT_TIMEZONE = ZoneInfo("Asia/Kolkata")


def get_restaurant(db: Session, restaurant_id: int):
    restaurant = db.get(Restaurant, restaurant_id)

    if restaurant is None or not restaurant.is_active:
        raise HTTPException( status_code=404, detail="Restaurant not found" )

    return restaurant


def get_owned_restaurant( db: Session, restaurant_id: int, owner: User ):
    restaurant = get_restaurant(db, restaurant_id)

    if restaurant.owner_id != owner.id:
        raise HTTPException( status_code=403,
            detail="You cannot manage this restaurant" )

    if not owner.is_approved:
        raise HTTPException( status_code=403, detail="Admin approval required" )

    return restaurant


def is_restaurant_open(restaurant: Restaurant):
    current_time = datetime.now( RESTAURANT_TIMEZONE ).time().replace(tzinfo=None)

    return ( restaurant.is_active and not restaurant.is_temporarily_closed 
             and restaurant.opening_time <= current_time < restaurant.closing_time )


def restaurant_response(restaurant: Restaurant):
    return {"id": restaurant.id,
            "owner_id": restaurant.owner_id,
            "name": restaurant.name,
            "cuisine_type": restaurant.cuisine_type,
            "address": restaurant.address,
            "latitude": restaurant.latitude,
            "longitude": restaurant.longitude,
            "opening_time": restaurant.opening_time,
            "closing_time": restaurant.closing_time,
            "is_temporarily_closed": restaurant.is_temporarily_closed,
            "delivery_radius_km": restaurant.delivery_radius_km,
            "min_order_value": restaurant.min_order_value,
            "avg_preparation_minutes": restaurant.avg_preparation_minutes,
            "average_rating": restaurant.average_rating,
            "is_active": restaurant.is_active,
            "is_open": is_restaurant_open(restaurant),
            "created_at": restaurant.created_at }


def get_owned_item(db: Session,item_id: int,owner: User):
    item = db.get(MenuItem, item_id)

    if item is None or item.is_deleted:
        raise HTTPException( status_code=404,detail="Menu item not found")

    get_owned_restaurant(db, item.restaurant_id, owner)
    return item


def validate_category( db: Session,restaurant_id: int, category_id: int ):
    category = db.get(MenuCategory, category_id)

    if category is None or category.restaurant_id != restaurant_id:
        raise HTTPException(status_code=400,detail="Category does not belong to this restaurant")

    return category


# --------------------------------------
# CREATE RESTAURANT
# --------------------------------------

@router.post( "/restaurants", response_model=RestaurantResponse,status_code=status.HTTP_201_CREATED)
def create_restaurant(data: RestaurantCreate,db: Session = Depends(get_db),owner: User = Depends(require_roles("restaurant_owner"))):
   
    if not owner.is_approved:
        raise HTTPException(status_code=403,detail="Admin approval required")

    restaurant = Restaurant(owner_id=owner.id,**data.model_dump())

    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    return restaurant_response(restaurant)


# --------------------------------------
# MY RESTAURANTS
# --------------------------------------

@router.get("/restaurants/me",response_model=list[RestaurantResponse])
def my_restaurants(db: Session = Depends(get_db),owner: User = Depends(require_roles("restaurant_owner"))):

    restaurants = db.scalars( select(Restaurant).where( Restaurant.owner_id == owner.id,
                                                       Restaurant.is_active.is_(True)).order_by(Restaurant.id)).all()

    return [restaurant_response(r) for r in restaurants]


# --------------------------------------
# GET RESTAURANT DETAILS
# --------------------------------------

@router.get("/restaurants/{restaurant_id}",response_model=RestaurantResponse)
def restaurant_details( restaurant_id: int,db: Session = Depends(get_db)):
    restaurant = get_restaurant(db, restaurant_id)
    return restaurant_response(restaurant)


# --------------------------------------
# UPDATE RESTAURANT
# --------------------------------------

@router.put("/restaurants/{restaurant_id}",response_model=RestaurantResponse)
def update_restaurant( restaurant_id: int, data: RestaurantUpdate,db: Session = Depends(get_db),
                       owner: User = Depends(require_roles("restaurant_owner"))):
    restaurant = get_owned_restaurant( db, restaurant_id, owner )

    updates = data.model_dump(exclude_unset=True)

    for key, value in updates.items():
        if value is None:
            raise HTTPException(status_code=422,detail=f"{key} cannot be null")
        setattr(restaurant, key, value)

    if restaurant.opening_time >= restaurant.closing_time:
        raise HTTPException( status_code=422, detail="Opening time must be before closing time")

    db.commit()
    db.refresh(restaurant)

    return restaurant_response(restaurant)


# --------------------------------------
# OPEN / CLOSE RESTAURANT
# --------------------------------------

@router.put("/restaurants/{restaurant_id}/open-status",response_model=RestaurantResponse)
def update_open_status(restaurant_id: int, data: OpenStatusUpdate,db: Session = Depends(get_db),
                       owner: User = Depends(require_roles("restaurant_owner"))):
    restaurant = get_owned_restaurant( db, restaurant_id, owner)

    restaurant.is_temporarily_closed = ( data.is_temporarily_closed )

    db.commit()
    db.refresh(restaurant)

    return restaurant_response(restaurant)


# --------------------------------------
# CREATE MENU CATEGORY
# --------------------------------------

@router.post("/restaurants/{restaurant_id}/categories",response_model=CategoryResponse,status_code=status.HTTP_201_CREATED)
def create_category(restaurant_id: int,data: CategoryCreate,db: Session = Depends(get_db),
                    owner: User = Depends(require_roles("restaurant_owner"))):
    
    get_owned_restaurant(db, restaurant_id, owner)

    existing = db.scalar(select(MenuCategory).where(MenuCategory.restaurant_id == restaurant_id,MenuCategory.name == data.name))

    if existing:
        raise HTTPException(status_code=409,detail="Category already exists")

    category = MenuCategory(restaurant_id=restaurant_id,name=data.name)

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


# --------------------------------------
# CREATE MENU ITEM
# --------------------------------------

@router.post("/restaurants/{restaurant_id}/menu-items",response_model=MenuItemResponse,
              status_code=status.HTTP_201_CREATED)
def create_menu_item( restaurant_id: int,data: MenuItemCreate,db: Session = Depends(get_db),
                      owner: User = Depends(require_roles("restaurant_owner"))):
    get_owned_restaurant(db, restaurant_id, owner)

    validate_category( db, restaurant_id, data.category_id )

    item = MenuItem( restaurant_id=restaurant_id,**data.model_dump())

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# --------------------------------------
# VIEW MENU GROUPED BY CATEGORY
# --------------------------------------

@router.get("/restaurants/{restaurant_id}/menu",response_model=RestaurantMenuResponse)
def get_restaurant_menu( restaurant_id: int,db: Session = Depends(get_db)):
    restaurant = get_restaurant(db, restaurant_id)

    categories = db.scalars(
        select(MenuCategory).where( MenuCategory.restaurant_id == restaurant_id).order_by(MenuCategory.id) ).all()

    result = []

    for category in categories:
        items = db.scalars( select(MenuItem).where( MenuItem.restaurant_id == restaurant_id,MenuItem.category_id == category.id,
                                    MenuItem.is_deleted.is_(False)).order_by(MenuItem.id)).all()

        result.append({ "id": category.id,"restaurant_id": category.restaurant_id,
                        "name": category.name,"items": items})

    return { "restaurant_id": restaurant.id, "restaurant_name": restaurant.name, "categories": result }


# --------------------------------------
# UPDATE MENU ITEM
# --------------------------------------

@router.put( "/menu-items/{item_id}", response_model=MenuItemResponse)
def update_menu_item( item_id: int,data: MenuItemUpdate,db: Session = Depends(get_db),
                      owner: User = Depends(require_roles("restaurant_owner"))):
    item = get_owned_item(db, item_id, owner)

    updates = data.model_dump(exclude_unset=True)

    if "category_id" in updates:
        if updates["category_id"] is None:
            raise HTTPException( status_code=422,detail="category_id cannot be null")

        validate_category( db, item.restaurant_id, updates["category_id"])

    for key, value in updates.items():
        if key != "description" and value is None:
            raise HTTPException(
                status_code=422,
                detail=f"{key} cannot be null"
            )

        setattr(item, key, value)

    db.commit()
    db.refresh(item)

    return item


# --------------------------------------
# CHANGE ITEM AVAILABILITY
# --------------------------------------

@router.put( "/menu-items/{item_id}/availability", response_model=MenuItemResponse )
def update_item_availability( item_id: int,data: AvailabilityUpdate,db: Session = Depends(get_db),
                              owner: User = Depends(require_roles("restaurant_owner"))):
    item = get_owned_item(db, item_id, owner)

    item.is_available = data.is_available

    db.commit()
    db.refresh(item)

    return item


# --------------------------------------
# SOFT DELETE MENU ITEM
# --------------------------------------

@router.delete("/menu-items/{item_id}")
def delete_menu_item( item_id: int,db: Session = Depends(get_db), owner: User = Depends(require_roles("restaurant_owner"))):
    item = get_owned_item(db, item_id, owner)

    item.is_deleted = True
    item.is_available = False

    db.commit()

    return { "message": "Menu item deleted successfully" }





# -----------------------------------
# SEARCH NEARBY RESTAURANTS
# -----------------------------------

@router.get("/restaurants/nearby")
def nearby_restaurants( latitude: float = Query(ge=-90, le=90),longitude: float = Query(ge=-180, le=180),
                       cuisine_type: str | None = None, min_rating: float | None = Query(default=None, ge=0, le=5),
                       skip: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
                       sort_by: str = Query(default="distance", pattern="^(distance|rating|estimated_delivery_minutes)$"),
                       order: str = Query(default="asc", pattern="^(asc|desc)$"),
                       db: Session = Depends(get_db)):
    restaurants = db.scalars(
        select(Restaurant).where( Restaurant.is_active.is_(True),Restaurant.is_temporarily_closed.is_(False))).all()

    results = []

    for restaurant in restaurants:

        # Exclude restaurants outside operating hours.
        if not is_restaurant_open(restaurant):
            continue

        distance = haversine_distance( latitude,longitude,restaurant.latitude,restaurant.longitude)

        # Each restaurant has its own delivery radius.
        if distance > float(restaurant.delivery_radius_km):
            continue

        if cuisine_type and restaurant.cuisine_type.casefold() != cuisine_type.strip().casefold():
            continue
        if min_rating is not None and float(restaurant.average_rating or 0) < min_rating:
            continue

        eta = estimated_delivery_minutes(distance,restaurant.avg_preparation_minutes)

        results.append({ "id": restaurant.id,
                         "name": restaurant.name,
                         "cuisine_type": restaurant.cuisine_type,
                         "address": restaurant.address,
                         "latitude": restaurant.latitude,
                         "longitude": restaurant.longitude,
                         "distance_km": round(distance, 2),
                         "estimated_delivery_minutes": eta,
                         "average_rating": float( restaurant.average_rating or 0 ),
                         "delivery_radius_km": float( restaurant.delivery_radius_km ),
                         "is_open": True })

    sort_key = {
        "distance": "distance_km",
        "rating": "average_rating",
        "estimated_delivery_minutes": "estimated_delivery_minutes",
    }[sort_by]
    results.sort(key=lambda result: result[sort_key], reverse=order == "desc")

    return {"total": len(results),"restaurants": results[skip:skip + limit] }
