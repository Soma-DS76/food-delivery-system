from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Order, Payment


def initiate_payment(db: Session,order_id: int,customer_id: int):
    order = db.scalar(select(Order)
                      .where(Order.id == order_id)
                      .with_for_update())

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.customer_id != customer_id:
        raise HTTPException(status_code=403,detail="You cannot pay for another customer's order")

    if order.status in {"Cancelled", "Rejected", "Delivered"}:
        raise HTTPException(status_code=400,detail="Payment cannot be initiated for this order status")

    existing = db.scalar(select(Payment).where(Payment.order_id == order_id))
    if existing:
        return existing

    if order.payment_method == "COD":
        raise HTTPException(status_code=409, detail="COD orders are paid on delivery")

    # This endpoint is a mock gateway. Successful initiation simulates a
    # successful online payment; no real payment provider is contacted.
    payment = Payment(order_id=order.id,customer_id=customer_id,amount=order.grand_total,
                      payment_method=order.payment_method,provider="mock",status="Paid")
    order.payment_status = "Paid"

    try:
        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def get_customer_payment(db: Session,order_id: int,customer_id: int):

    payment = db.scalar(select(Payment).where(Payment.order_id == order_id,Payment.customer_id == customer_id))

    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    return payment


def cancel_pending_payment(db: Session,order_id: int,customer_id: int):
   
    payment = db.scalar(select(Payment)
                        .where(Payment.order_id == order_id,Payment.customer_id == customer_id)
                        .with_for_update())

    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != "Pending":
        raise HTTPException(status_code=409,detail="Only pending payments can be cancelled")

    try:
        payment.status = "Cancelled"
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise