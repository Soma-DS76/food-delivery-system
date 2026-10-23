
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_roles
from app.models.entities import User
from app.schemas.analytics import (DashboardSummary,OrderStatusSummary,DailyRevenue)
from app.services.analytics import (get_dashboard_summary, get_order_status_summary, get_daily_revenue,
                                     get_top_restaurants, get_coupon_usage_report,
                                     get_restaurant_sales_report, get_partner_summary)

router = APIRouter(prefix="/admin/analytics",tags=["Admin Analytics"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db),admin: User = Depends(require_roles("admin"))):
    return get_dashboard_summary(db)


@router.get("/order-statuses", response_model=list[OrderStatusSummary])
def order_statuses(db: Session = Depends(get_db),admin: User = Depends(require_roles("admin"))):
    return get_order_status_summary(db)


@router.get("/daily-revenue", response_model=list[DailyRevenue])
def daily_revenue(days: int = Query(default=7, ge=1, le=90),db: Session = Depends(get_db),admin: User = Depends(require_roles("admin"))):
    return get_daily_revenue(db, days)




@router.get("/top-restaurants")
def top_restaurants(limit: int = Query(default=10, ge=1, le=100),
                   db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    return get_top_restaurants(db, limit)


@router.get("/coupon-usage")
def coupon_usage(limit: int = Query(default=100, ge=1, le=500),
                 db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    return get_coupon_usage_report(db, limit)


@router.get("/restaurant-sales")
def restaurant_sales(limit: int = Query(default=100, ge=1, le=500),
                     db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    return get_restaurant_sales_report(db, limit)


@router.get("/delivery-partners")
def delivery_partner_summary(limit: int = Query(default=100, ge=1, le=500),
                             db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    return get_partner_summary(db, limit)
