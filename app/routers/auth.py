
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User
from app.schemas.auth import ( RegisterRequest, LoginRequest,UserResponse, TokenResponse )
from app.auth.security import ( hash_password, verify_password, create_access_token, get_current_user )

router = APIRouter(prefix="/auth", tags=["Authentication"])


def serialize_user(user: User):
    return { "id": user.id, "name": user.name, "email": user.email, "phone": user.phone,
             "role": getattr(user.role, "value", user.role), "is_active": user.is_active, 
             "is_approved": user.is_approved }


@router.post( "/register", response_model=UserResponse,status_code=201 )
def register(data: RegisterRequest, db: Session = Depends(get_db)):

    email = data.email.strip().lower()

    existing_email = db.scalar( select(User).where(func.lower(User.email) == email) )

    if existing_email:
        raise HTTPException( status_code=409, detail="Email already registered" )

    existing_phone = db.scalar( select(User).where(User.phone == data.phone) )

    if existing_phone:
        raise HTTPException( status_code=409, detail="Phone number already registered" )

    user = User( name=data.name, email=email, phone=data.phone, password_hash=hash_password(data.password), 
                 role=data.role, is_active=True, is_approved=(data.role == "customer") )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return serialize_user(user)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):

    email = data.email.strip().lower()

    user = db.scalar( select(User).where(func.lower(User.email) == email) )

    if not user or not verify_password( data.password, user.password_hash ):
        raise HTTPException( status_code=401, detail="Invalid email or password" )

    if not user.is_active:
        raise HTTPException( status_code=403, detail="Account is inactive" )

    token = create_access_token(user.id)

    return { "access_token": token, "token_type": "bearer", "expires_in": 1800 }


@router.get("/me", response_model=UserResponse)
def get_profile(user: User = Depends(get_current_user)):
    return serialize_user(user)
