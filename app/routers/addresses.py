
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User, Address
from app.auth.security import require_roles
from app.schemas.address import ( AddressCreate,AddressUpdate,AddressResponse)

router = APIRouter( prefix="/addresses",tags=["Customer Addresses"])


def get_customer_address(db, address_id, customer_id):
    address = db.scalar( select(Address).where( Address.id == address_id, Address.customer_id == customer_id ))

    if not address:
        raise HTTPException( status_code=404, detail="Address not found" )

    return address


def clear_default_address(db, customer_id):
    db.execute( update(Address) .where(Address.customer_id == customer_id).values(is_default=False))


def lock_customer(db, customer_id):
    db.execute( select(User.id) .where(User.id == customer_id) .with_for_update()).first()


@router.post("", response_model=AddressResponse, status_code=201)
def create_address( data: AddressCreate, db: Session = Depends(get_db),
                    customer: User = Depends(require_roles("customer"))):
    lock_customer(db, customer.id)

    first_address = db.scalar( select(Address.id) .where(Address.customer_id == customer.id).limit(1) ) is None

    make_default = first_address or data.is_default

    if make_default:
        clear_default_address(db, customer.id)

    address = Address( customer_id=customer.id,**data.model_dump(exclude={"is_default"}),is_default=make_default )

    db.add(address)
    db.commit()
    db.refresh(address)

    return address


@router.get("", response_model=list[AddressResponse])
def get_addresses( db: Session = Depends(get_db), customer: User = Depends(require_roles("customer"))):

    return db.scalars( select(Address) .where(Address.customer_id == customer.id)
                      .order_by( Address.is_default.desc(), Address.id.asc() ) ).all()


@router.put("/{address_id}", response_model=AddressResponse)
def update_address( address_id: int, data: AddressUpdate, db: Session = Depends(get_db), 
                    customer: User = Depends(require_roles("customer"))):
    lock_customer(db, customer.id)
    address = get_customer_address(db, address_id, customer.id)

    changes = data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if value is None:
            raise HTTPException( status_code=422, detail=f"{field} cannot be null" )

    if changes.pop("is_default", False):
        clear_default_address(db, customer.id)
        address.is_default = True

    for field, value in changes.items():
        setattr(address, field, value)

    db.commit()
    db.refresh(address)

    return address


@router.delete("/{address_id}")
def delete_address( address_id: int, db: Session = Depends(get_db), 
                    customer: User = Depends(require_roles("customer"))):
    lock_customer(db, customer.id)
    address = get_customer_address(db, address_id, customer.id)

    was_default = address.is_default

    db.delete(address)
    db.flush()

    if was_default:
        next_address = db.scalar( select(Address) .where(Address.customer_id == customer.id)
                                  .order_by(Address.id) .limit(1))

        if next_address:
            next_address.is_default = True

    db.commit()

    return {"message": "Address deleted successfully"}


@router.put("/{address_id}/default", response_model=AddressResponse)
def set_default_address( address_id: int, db: Session = Depends(get_db), 
                         customer: User = Depends(require_roles("customer"))):
    lock_customer(db, customer.id)
    address = get_customer_address(db, address_id, customer.id)

    clear_default_address(db, customer.id)
    address.is_default = True

    db.commit()
    db.refresh(address)

    return address
