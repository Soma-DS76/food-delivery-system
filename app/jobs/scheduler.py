"""Background automation for order, delivery-offer and coupon housekeeping.

These are database-backed demo jobs. Run one application worker only unless a
separate scheduler process or distributed lock is configured; APScheduler is
not a distributed scheduler.
"""
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.database import SessionLocal
from app.models.entities import (
    Order, OrderStatusHistory, DeliveryOffer, DeliveryPartner, Coupon,
    User, Notification,
)
from app.services.delivery import assign_next_partner
from app.services.notifications import create_notification, notify_order_status

scheduler = BackgroundScheduler(timezone="UTC")


def _now():
    return datetime.utcnow()


def auto_reject_stale_orders():
    """Reject restaurant orders that remain Placed for more than five minutes."""
    with SessionLocal() as db:
        cutoff = _now() - timedelta(minutes=5)
        orders = db.scalars(select(Order).where(Order.status == "Placed", Order.placed_at <= cutoff)).all()
        for order in orders:
            old_status = order.status
            order.status = "Rejected"
            if order.payment_method == "ONLINE" and order.payment_status == "Paid":
                order.payment_status = "Refunded"
                from app.models.entities import Payment
                payment = db.scalar(select(Payment).where(Payment.order_id == order.id))
                if payment:
                    payment.status = "Refunded"
            db.add(OrderStatusHistory(order_id=order.id, old_status=old_status,
                                      new_status="Rejected", changed_by="System",
                                      reason="Automatically rejected after 5 minutes"))
            notify_order_status(db, order)
        db.commit()


def expire_offers_and_retry_assignment():
    """Expire 30-second offers and try the next eligible partner."""
    now = _now()
    with SessionLocal() as db:
        expired = db.scalars(select(DeliveryOffer).where(
            DeliveryOffer.status == "Pending", DeliveryOffer.expires_at <= now
        )).all()
        affected_order_ids = {offer.order_id for offer in expired}
        for offer in expired:
            offer.status = "Expired"
        db.flush()
        for order_id in affected_order_ids:
            order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
            if order and order.delivery_partner_id is None and order.status in {"Accepted", "Preparing", "ReadyForPickup"}:
                assign_next_partner(db, order_id)
        db.commit()


def retry_unassigned_orders_and_alert_admins():
    """Retry partner assignment and notify admins after 15 minutes unassigned."""
    now = _now()
    with SessionLocal() as db:
        orders = db.scalars(select(Order).where(
            Order.delivery_partner_id.is_(None),
            Order.status.in_(["Accepted", "Preparing", "ReadyForPickup"]),
        )).all()
        admins = db.scalars(select(User).where(User.role == "admin", User.is_active.is_(True))).all()
        for order in orders:
            assign_next_partner(db, order.id)
            if order.placed_at and order.placed_at <= now - timedelta(minutes=15):
                already_alerted = db.scalar(select(Notification.id).where(
                    Notification.order_id == order.id,
                    Notification.notification_type == "unassigned_order_alert",
                ).limit(1))
                if not already_alerted:
                    for admin in admins:
                        create_notification(db, admin.id, "Unassigned delivery order",
                                            f"Order {order.order_number} has no delivery partner after 15 minutes.",
                                            "unassigned_order_alert", order.id)
        db.commit()


def mark_stale_partners_offline():
    """Set partners offline when no location heartbeat has arrived for 30 minutes."""
    cutoff = _now() - timedelta(minutes=30)
    with SessionLocal() as db:
        partners = db.scalars(select(DeliveryPartner).where(
            DeliveryPartner.is_online.is_(True),
            DeliveryPartner.last_location_at.is_not(None),
            DeliveryPartner.last_location_at < cutoff,
        )).all()
        for partner in partners:
            partner.is_online = False
        db.commit()


def expire_coupons():
    """Deactivate coupons whose validity window has ended."""
    with SessionLocal() as db:
        coupons = db.scalars(select(Coupon).where(Coupon.is_active.is_(True), Coupon.valid_to <= _now())).all()
        for coupon in coupons:
            coupon.is_active = False
        db.commit()


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(auto_reject_stale_orders, "interval", minutes=1,
                      id="auto_reject_stale_orders", replace_existing=True, max_instances=1)
    scheduler.add_job(expire_offers_and_retry_assignment, "interval", seconds=10,
                      id="expire_delivery_offers", replace_existing=True, max_instances=1)
    scheduler.add_job(retry_unassigned_orders_and_alert_admins, "interval", minutes=1,
                      id="retry_unassigned_orders", replace_existing=True, max_instances=1)
    scheduler.add_job(mark_stale_partners_offline, "interval", minutes=5,
                      id="mark_stale_partners_offline", replace_existing=True, max_instances=1)
    scheduler.add_job(expire_coupons, "cron", hour=0, minute=5,
                      id="expire_coupons_daily", replace_existing=True, max_instances=1)
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
