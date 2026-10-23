
from datetime import datetime, timedelta, timezone
import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import User

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

if not SECRET_KEY or SECRET_KEY == "REPLACE_WITH_LONG_RANDOM_SECRET":
    raise RuntimeError("Set a secure JWT_SECRET_KEY in .env")

password_hash = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expires,
        "type": "access"
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user( credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),db: Session = Depends(get_db)):
   
    unauthorized = HTTPException( status_code=status.HTTP_401_UNAUTHORIZED,
                                  detail="Invalid or expired token",
                                  headers={"WWW-Authenticate": "Bearer"})

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode( credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM] )

        if payload.get("type") != "access":
            raise unauthorized

        user_id = int(payload.get("sub"))

    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized

    user = db.get(User, user_id)

    if not user or not user.is_active:
        raise unauthorized

    return user


def require_roles(*allowed_roles):
    def check_role(user: User = Depends(get_current_user)):
        role = getattr(user.role, "value", user.role)

        if role not in allowed_roles:
            raise HTTPException( status_code=403, detail="You do not have permission" )

        return user

    return check_role
