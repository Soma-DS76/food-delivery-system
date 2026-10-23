
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from dotenv import load_dotenv 
load_dotenv()


from app.database import get_db

from app.routers import (auth,admin,restaurants,addresses,cart,coupons,cart_coupons,
                         orders,restaurant_orders,delivery ,tracking ,notifications,
                         analytics,ratings,payments,reports)


 

app = FastAPI( title="Food Delivery System API",description="FastAPI Food Delivery Backend",version="0.3.0")

 
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(restaurants.router)
app.include_router(addresses.router)
app.include_router(cart.router)
app.include_router(coupons.router)
app.include_router(cart_coupons.router)
app.include_router(orders.router)
app.include_router(restaurant_orders.router)
app.include_router(delivery.router)
app.include_router(tracking.router)
app.include_router(notifications.router)
app.include_router(analytics.router)
app.include_router(ratings.router)
app.include_router(payments.router)
app.include_router(reports.router)



@app.on_event("startup")
def start_background_jobs():
    from app.jobs.scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
def stop_background_jobs():
    from app.jobs.scheduler import stop_scheduler
    stop_scheduler()


@app.get("/")
def home():
    return { "message": "Food Delivery API running", "level":15}


@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "connected"}
