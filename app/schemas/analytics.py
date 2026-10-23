
from decimal import Decimal
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_customers: int
    total_restaurants: int
    total_orders: int
    delivered_orders: int
    cancelled_or_rejected_orders: int
    pending_orders: int
    total_revenue: Decimal


class OrderStatusSummary(BaseModel):
    status: str
    count: int


class DailyRevenue(BaseModel):
    date: str
    orders: int
    revenue: Decimal
