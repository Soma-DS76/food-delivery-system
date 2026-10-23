from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_roles
from app.schemas.payment import PaymentResponse
from app.services.payments import (initiate_payment,get_customer_payment,cancel_pending_payment)

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/{order_id}/pay", response_model=PaymentResponse)
def pay_for_order(order_id: int,db: Session = Depends(get_db),user=Depends(require_roles("customer"))):
    return initiate_payment(db, order_id, user.id)


@router.get("/{order_id}", response_model=PaymentResponse)
def payment_status(order_id: int,db: Session = Depends(get_db),user=Depends(require_roles("customer"))):
    return get_customer_payment(db, order_id, user.id)


@router.post("/{order_id}/cancel", response_model=PaymentResponse)
def cancel_payment(order_id: int,db: Session = Depends(get_db),user=Depends(require_roles("customer"))):
    return cancel_pending_payment(db, order_id, user.id)