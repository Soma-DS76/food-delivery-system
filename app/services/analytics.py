
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.models.entities import User, Restaurant, Order


def get_dashboard_summary(db: Session):
    total_customers = db.scalar(
        select(func.count(User.id)).where(User.role == "customer")) or 0

    total_restaurants = db.scalar(select(func.count(Restaurant.id)).where(Restaurant.is_active.is_(True))) or 0

    total_orders = db.scalar(select(func.count(Order.id))) or 0

    delivered_orders = db.scalar(
        select(func.count(Order.id)).where(Order.status == "Delivered")) or 0

    cancelled_or_rejected = db.scalar(select(func.count(Order.id)).where(Order.status.in_(["Cancelled", "Rejected"]))) or 0

    pending_orders = db.scalar(
        select(func.count(Order.id)).where(
            Order.status.in_([  "Placed",
                                "Accepted",
                                "Preparing",
                                "ReadyForPickup",
                                "PickedUp",
                                "OutForDelivery"]))) or 0

    # Revenue only includes successfully delivered orders.
    revenue = db.scalar( select(func.coalesce(func.sum(Order.grand_total), 0)).where(
            Order.status == "Delivered",
            Order.payment_status == "Paid")) or Decimal("0")

    return {"total_customers": total_customers,
            "total_restaurants": total_restaurants,
            "total_orders": total_orders,
            "delivered_orders": delivered_orders,
            "cancelled_or_rejected_orders": cancelled_or_rejected,
            "pending_orders": pending_orders,
            "total_revenue": revenue}


def get_order_status_summary(db: Session):
    rows = db.execute(select(Order.status,func.count(Order.id).label("count"))
                      .group_by(Order.status)
                      .order_by(Order.status)).all()

    return [ {"status": status, "count": count} for status, count in rows]


def get_daily_revenue(db: Session, days: int = 7):
    start_date = date.today() - timedelta(days=days - 1)

    rows = db.execute(
        select( func.date(Order.placed_at).label("order_date"),
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.grand_total), 0).label("revenue"))
        .where( Order.placed_at >= start_date, Order.status == "Delivered", Order.payment_status == "Paid",
               ) .group_by(func.date(Order.placed_at)).order_by(func.date(Order.placed_at))).all()

    return [{   "date": str(order_date),"orders": orders,"revenue": revenue } for order_date, orders, revenue in rows ]


def get_top_restaurants(db: Session, limit: int = 10,
                        from_date: date | None = None, to_date: date | None = None):
    statement = (
        select(Restaurant.id, Restaurant.name, func.count(Order.id).label("orders"),
               func.coalesce(func.sum(Order.grand_total), 0).label("sales"))
        .join(Order, Order.restaurant_id == Restaurant.id)
        .where(Order.status == "Delivered")
        .group_by(Restaurant.id, Restaurant.name)
        .order_by(func.count(Order.id).desc(), func.sum(Order.grand_total).desc())
    )
    if from_date is not None:
        statement = statement.where(Order.placed_at >= datetime.combine(from_date, time.min))
    if to_date is not None:
        statement = statement.where(Order.placed_at < datetime.combine(to_date + timedelta(days=1), time.min))
    rows = db.execute(statement.limit(limit)).all()
    return [{"restaurant_id": rid, "restaurant_name": name, "delivered_orders": count,
             "sales": sales} for rid, name, count, sales in rows]


def get_coupon_usage_report(db: Session, limit: int = 100, restaurant_owner_id: int | None = None,
                            from_date: date | None = None, to_date: date | None = None):
    from app.models.entities import Coupon, CouponUsage
    statement = (
        select(Coupon.id, Coupon.code, func.count(CouponUsage.id).label("usage_count"),
               func.coalesce(func.sum(Order.discount_amount), 0).label("total_discount"),
               func.coalesce(func.sum(Order.grand_total), 0).label("revenue"))
        .outerjoin(CouponUsage, CouponUsage.coupon_id == Coupon.id)
        .outerjoin(Order, Order.id == CouponUsage.order_id)
        .group_by(Coupon.id, Coupon.code)
        .order_by(func.count(CouponUsage.id).desc(), Coupon.code)
    )
    if restaurant_owner_id is not None:
        statement = statement.join(Restaurant, Coupon.restaurant_id == Restaurant.id).where(
            Restaurant.owner_id == restaurant_owner_id)
    if from_date is not None:
        statement = statement.where(Order.placed_at >= datetime.combine(from_date, time.min))
    if to_date is not None:
        statement = statement.where(Order.placed_at < datetime.combine(to_date + timedelta(days=1), time.min))
    rows = db.execute(statement.limit(limit)).all()
    return [{"coupon_id": cid, "code": code, "usage_count": count,
             "total_discount_given": discount, "revenue": revenue}
            for cid, code, count, discount, revenue in rows]


def get_restaurant_sales_report(db: Session, limit: int = 100,
                                restaurant_owner_id: int | None = None):
    statement = (
        select(Restaurant.id, Restaurant.name, func.count(Order.id).label("orders"),
               func.coalesce(func.sum(Order.grand_total), 0).label("sales"))
        .outerjoin(Order, Order.restaurant_id == Restaurant.id)
        .where((Order.status == "Delivered") | (Order.id.is_(None)))
        .group_by(Restaurant.id, Restaurant.name)
        .order_by(func.sum(Order.grand_total).desc())
    )
    if restaurant_owner_id is not None:
        statement = statement.where(Restaurant.owner_id == restaurant_owner_id)
    rows = db.execute(statement.limit(limit)).all()
    return [{"restaurant_id": rid, "restaurant_name": name, "delivered_orders": count,
             "sales": sales} for rid, name, count, sales in rows]


def get_partner_summary(db: Session, limit: int = 100):
    from app.models.entities import DeliveryPartner, User
    rows = db.execute(
        select(DeliveryPartner.id, User.name, DeliveryPartner.is_online,
               func.count(Order.id).label("delivered_orders"))
        .join(User, User.id == DeliveryPartner.user_id)
        .outerjoin(Order, (Order.delivery_partner_id == DeliveryPartner.id) & (Order.status == "Delivered"))
        .group_by(DeliveryPartner.id, User.name, DeliveryPartner.is_online)
        .order_by(func.count(Order.id).desc())
        .limit(limit)
    ).all()
    return [{"partner_id": pid, "partner_name": name, "is_online": online,
             "delivered_orders": count} for pid, name, online, count in rows]
