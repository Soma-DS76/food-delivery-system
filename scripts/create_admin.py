
import getpass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.entities import User
from app.auth.security import hash_password


def main():
    email = input("Admin email: ").strip().lower()
    name = input("Admin name: ").strip()
    phone = input("Admin phone (10 digits): ").strip()
    password = getpass.getpass("Admin password: ")

    if ( not email or not name or len(phone) != 10 or not phone.isdigit() or len(password) < 8 ):
        print("Invalid admin details")
        return

    with SessionLocal() as db:
        existing = db.scalar( select(User).where(User.email == email) )

        if existing:
            print("Admin email already exists")
            return

        admin = User( name=name, email=email, phone=phone, password_hash=hash_password(password),
                      role="admin", is_active=True,is_approved=True )

        db.add(admin)

        try:
            db.commit()
            print("Admin account created successfully")
        except IntegrityError:
            db.rollback()
            print("Email or phone already exists")


if __name__ == "__main__":
    main()
