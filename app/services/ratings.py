from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.entities import Order, Rating, Restaurant


def create_rating(db: Session, customer_id: int, order_id: int,
                  restaurant_rating: int, partner_rating: int, comment: str | None):
    order = db.scalar(select(Order).where(Order.id == order_id))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="You cannot review another customer's order")
    if order.status != "Delivered":
        raise HTTPException(status_code=400, detail="You can review only delivered orders")
    if order.delivery_partner_id is None:
        raise HTTPException(status_code=409, detail="This order has no delivery partner to rate")
    if db.scalar(select(Rating.id).where(Rating.order_id == order_id)):
        raise HTTPException(status_code=409, detail="This order has already been reviewed")

    rating = Rating(order_id=order.id, restaurant_rating=restaurant_rating,
                    partner_rating=partner_rating, comment=comment)
    try:
        db.add(rating)
        db.flush()
        average = db.scalar(
            select(func.avg(Rating.restaurant_rating))
            .join(Order, Order.id == Rating.order_id)
            .where(Order.restaurant_id == order.restaurant_id)
        )
        restaurant = db.get(Restaurant, order.restaurant_id)
        if restaurant is not None:
            restaurant.average_rating = round(float(average or 0), 2)
        db.commit()
        db.refresh(rating)
        return rating
    except Exception:
        db.rollback()
        raise


def get_restaurant_rating_summary(db: Session, restaurant_id: int):
    average, count = db.execute(
        select(func.avg(Rating.restaurant_rating), func.count(Rating.id))
        .join(Order, Order.id == Rating.order_id)
        .where(Order.restaurant_id == restaurant_id)
    ).one()
    return {"restaurant_id": restaurant_id,
            "average_rating": round(float(average or 0), 2),
            "total_reviews": count}
