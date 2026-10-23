from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import get_current_user, require_roles
from app.models.entities import Rating, Restaurant, Order
from app.schemas.rating import (RatingCreate,RatingResponse,RestaurantRatingSummary)
from app.services.ratings import (create_rating,get_restaurant_rating_summary)


router = APIRouter(tags=["Ratings"])


@router.post("/orders/{order_id}/rating", response_model=RatingResponse, status_code=201)
def submit_rating(order_id: int, data: RatingCreate,db: Session = Depends(get_db),
                  user=Depends(require_roles("customer"))):
    return create_rating(db=db, customer_id=user.id, order_id=order_id,
                         restaurant_rating=data.restaurant_rating, partner_rating=data.partner_rating, comment=data.comment)


@router.get("/ratings/restaurant/{restaurant_id}/summary",response_model=RestaurantRatingSummary)
def restaurant_rating_summary(restaurant_id: int,db: Session = Depends(get_db),):
    if db.get(Restaurant, restaurant_id) is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    return get_restaurant_rating_summary(db, restaurant_id)


@router.get("/restaurants/{restaurant_id}/ratings",response_model=list[RatingResponse])
def restaurant_reviews(restaurant_id: int,limit: int = Query(default=20, ge=1, le=100),
                       skip: int = Query(default=0, ge=0),db: Session = Depends(get_db)):
    if db.get(Restaurant, restaurant_id) is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    statement = (select(Rating).join(Order, Order.id == Rating.order_id)
                 .where(Order.restaurant_id == restaurant_id)
                 .order_by(Rating.created_at.desc()).offset(skip).limit(limit))

    return list(db.scalars(statement).all())


@router.get("/ratings/my-reviews", response_model=list[RatingResponse])
def my_reviews(db: Session = Depends(get_db),user=Depends(require_roles("customer"))):
    statement = (select(Rating).join(Order, Order.id == Rating.order_id)
                 .where(Order.customer_id == user.id).order_by(Rating.created_at.desc()))
    return list(db.scalars(statement).all())


@router.delete("/ratings/{rating_id}")
def delete_my_review(rating_id: int,db: Session = Depends(get_db),user=Depends(require_roles("customer"))):
    
    rating = db.get(Rating, rating_id)

    if rating is None:
        raise HTTPException(status_code=404, detail="Review not found")
    order = db.get(Order, rating.order_id)
    if order is None or order.customer_id != user.id:
        raise HTTPException(status_code=404, detail="Review not found")

    restaurant_id = order.restaurant_id

    try:
        db.delete(rating)
        db.flush()

        average = db.scalar(select(func.avg(Rating.restaurant_rating))
                            .join(Order, Order.id == Rating.order_id)
                            .where(Order.restaurant_id == restaurant_id))

        restaurant = db.get(Restaurant, restaurant_id)

        if restaurant is not None and hasattr(restaurant, "average_rating"):
            restaurant.average_rating = round(float(average or 0), 2)

        db.commit()
        return {"message": "Review deleted successfully"}

    except Exception:
        db.rollback()
        raise