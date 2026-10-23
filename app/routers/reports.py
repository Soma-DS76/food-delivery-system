
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import require_roles
from app.database import get_db
from app.models.entities import User, Order

from app.schemas.analytics import (DashboardSummary,OrderStatusSummary,DailyRevenue)

from app.services.analytics import (get_dashboard_summary,get_order_status_summary,get_daily_revenue,get_top_restaurants,
                                    get_coupon_usage_report,get_restaurant_sales_report)
from app.services.delivery import get_partner, calculate_earnings

router = APIRouter(prefix="/reports",tags=["Reports"])


@router.get("/admin-dashboard", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db),admin: User = Depends(require_roles("admin"))):
    return get_dashboard_summary(db)


@router.get("/order-statuses",response_model=list[OrderStatusSummary])
def order_statuses(db: Session = Depends(get_db),admin: User = Depends(require_roles("admin"))):
    return get_order_status_summary(db)


@router.get("/daily-revenue", response_model=list[DailyRevenue])
def daily_revenue(days: int = Query(7, ge=1, le=90),db: Session = Depends(get_db),
                  admin: User = Depends(require_roles("admin"))):
    return get_daily_revenue(db, days)


@router.get("/top-restaurants")
def top_restaurants(limit: int = Query(10, ge=1, le=100), from_date: date | None = None,
                    to_date: date | None = None, db: Session = Depends(get_db),
                    admin: User = Depends(require_roles("admin"))):
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not exceed to_date")
    return get_top_restaurants(db, limit, from_date, to_date)


@router.get("/coupon-usage")
def coupon_usage(limit: int = Query(100, ge=1, le=500), from_date: date | None = None,
                 to_date: date | None = None, db: Session = Depends(get_db),
                 viewer: User = Depends(require_roles("admin", "restaurant_owner"))):
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not exceed to_date")
    if getattr(viewer.role, "value", viewer.role) == "restaurant_owner":
        return get_coupon_usage_report(db, limit, restaurant_owner_id=viewer.id,
                                       from_date=from_date, to_date=to_date)
    return get_coupon_usage_report(db, limit, from_date=from_date, to_date=to_date)


@router.get("/restaurant-sales")
def restaurant_sales( limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db),
                      owner: User = Depends(require_roles("restaurant_owner"))):
    return get_restaurant_sales_report(db, limit, restaurant_owner_id=owner.id)


@router.get("/partner-summary")
def delivery_partners(from_date: date | None = None, to_date: date | None = None,
                      db: Session = Depends(get_db),
                      user: User = Depends(require_roles("delivery_partner"))):
    start = from_date or date.today()
    end = to_date or date.today()
    if start > end:
        raise HTTPException(status_code=422, detail="from_date must not exceed to_date")

    partner = get_partner(db, user)
    orders = db.scalars(select(Order).where(
        Order.delivery_partner_id == partner.id,
        Order.status == "Delivered",
        Order.delivered_at >= datetime.combine(start, time.min),
        Order.delivered_at < datetime.combine(end + timedelta(days=1), time.min),
    ).order_by(Order.delivered_at)).all()
    by_day: dict[str, dict[str, object]] = {}
    for order in orders:
        day = order.delivered_at.date().isoformat()
        summary = by_day.setdefault(day, {"date": day, "deliveries_completed": 0,
                                          "total_distance_km": 0.0, "earnings": Decimal("0.00")})
        summary["deliveries_completed"] += 1
        summary["total_distance_km"] += order.distance_km
        summary["earnings"] += calculate_earnings(order)
    return {"from_date": start, "to_date": end, "daily_summary": list(by_day.values())}
