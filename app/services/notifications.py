
from sqlalchemy.orm import Session
from app.models.entities import Notification


def create_notification(db: Session,user_id: int,title: str,message: str,notification_type: str,order_id: int | None = None ):
    
    notification = Notification(user_id=user_id,title=title,message=message,notification_type=notification_type,order_id=order_id)

    db.add(notification)
    db.flush()

    return notification


def notify_order_status(db: Session, order):
    messages = {
        "Accepted": ("Order Accepted","Your restaurant has accepted your order."),
        "Preparing": ("Preparing Your Food","Your food is being prepared."),
        "ReadyForPickup": ("Food Ready","Your food is ready for pickup."),
        "PickedUp": ( "Order Picked Up","Your delivery partner picked up your order."),
        "OutForDelivery": ("Out for Delivery","Your order is on the way."),
        "Delivered": ("Order Delivered","Your order has been delivered."),
        "Rejected": ("Order Rejected","The restaurant could not accept your order.")}

    details = messages.get(order.status)

    if details:
        title, message = details

        create_notification( db=db,user_id=order.customer_id,title=title,message=message,notification_type="order_status",order_id=order.id)
