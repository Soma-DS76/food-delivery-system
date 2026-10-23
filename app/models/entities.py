from datetime import datetime, time
from decimal import Decimal
from sqlalchemy import String, ForeignKey, Boolean, DateTime, Numeric, Integer, Float, Time, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

class User(TimestampMixin, Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(10), unique=True)
    role: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    restaurants: Mapped[list['Restaurant']] = relationship(back_populates='owner')
    addresses: Mapped[list['Address']] = relationship(back_populates='customer')
    cart: Mapped['Cart | None'] = relationship(back_populates='customer', uselist=False)
    orders: Mapped[list['Order']] = relationship(back_populates='customer')
    partner: Mapped['DeliveryPartner | None'] = relationship(back_populates='user', uselist=False)

class Restaurant(TimestampMixin, Base):
    __tablename__ = 'restaurants'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(150))
    cuisine_type: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    opening_time: Mapped[time] = mapped_column(Time)
    closing_time: Mapped[time] = mapped_column(Time)
    is_temporarily_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_radius_km: Mapped[float] = mapped_column(Float, default=5)
    min_order_value: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    avg_preparation_minutes: Mapped[int] = mapped_column(Integer, default=30)
    average_rating: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    owner: Mapped['User'] = relationship(back_populates='restaurants')
    categories: Mapped[list['MenuCategory']] = relationship(back_populates='restaurant')
    menu_items: Mapped[list['MenuItem']] = relationship(back_populates='restaurant')

class MenuCategory(TimestampMixin, Base):
    __tablename__ = 'menu_categories'
    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey('restaurants.id'))
    name: Mapped[str] = mapped_column(String(100))
    restaurant: Mapped['Restaurant'] = relationship(back_populates='categories')
    items: Mapped[list['MenuItem']] = relationship(back_populates='category')

class MenuItem(TimestampMixin, Base):
    __tablename__ = 'menu_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey('restaurants.id'))
    category_id: Mapped[int] = mapped_column(ForeignKey('menu_categories.id'))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10,2))
    is_veg: Mapped[bool] = mapped_column(Boolean)
    packaging_charge: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    restaurant: Mapped['Restaurant'] = relationship(back_populates='menu_items')
    category: Mapped['MenuCategory'] = relationship(back_populates='items')

class Address(TimestampMixin, Base):
    __tablename__ = 'addresses'
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    label: Mapped[str] = mapped_column(String(30))
    address_line: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100))
    pincode: Mapped[str] = mapped_column(String(6))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    customer: Mapped['User'] = relationship(back_populates='addresses')

class Cart(TimestampMixin, Base):
    __tablename__ = 'carts'
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True)
    restaurant_id: Mapped[int | None] = mapped_column(ForeignKey('restaurants.id'))
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey('coupons.id'))
    customer: Mapped['User'] = relationship(back_populates='cart')
    items: Mapped[list['CartItem']] = relationship(back_populates='cart')

class CartItem(TimestampMixin, Base):
    __tablename__ = 'cart_items'
    __table_args__ = (UniqueConstraint('cart_id', 'menu_item_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey('carts.id'))
    menu_item_id: Mapped[int] = mapped_column(ForeignKey('menu_items.id'))
    quantity: Mapped[int] = mapped_column(Integer)
    cart: Mapped['Cart'] = relationship(back_populates='items')

class Coupon(TimestampMixin, Base):
    __tablename__ = 'coupons'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    discount_type: Mapped[str] = mapped_column(String(20))
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10,2))
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(10,2))
    min_order_value: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    restaurant_id: Mapped[int | None] = mapped_column(ForeignKey('restaurants.id'))
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime] = mapped_column(DateTime)
    total_usage_limit: Mapped[int | None] = mapped_column(Integer)
    per_user_limit: Mapped[int | None] = mapped_column(Integer)
    first_order_only: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    usages: Mapped[list['CouponUsage']] = relationship(back_populates='coupon')

class DeliveryPartner(TimestampMixin, Base):
    __tablename__ = 'delivery_partners'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True)
    vehicle_type: Mapped[str] = mapped_column(String(30))
    vehicle_number: Mapped[str] = mapped_column(String(30), unique=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    current_latitude: Mapped[float | None] = mapped_column(Float)
    current_longitude: Mapped[float | None] = mapped_column(Float)
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped['User'] = relationship(back_populates='partner')
    deliveries: Mapped[list['Order']] = relationship(back_populates='delivery_partner')

class Order(TimestampMixin, Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(50), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    restaurant_id: Mapped[int] = mapped_column(ForeignKey('restaurants.id'))
    address_id: Mapped[int] = mapped_column(ForeignKey('addresses.id'))
    delivery_partner_id: Mapped[int | None] = mapped_column(ForeignKey('delivery_partners.id'))
    item_total: Mapped[Decimal] = mapped_column(Numeric(10,2))
    coupon_code: Mapped[str | None] = mapped_column(String(60))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    packaging_charges: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10,2), default=5)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    tip_amount: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(10,2))
    payment_method: Mapped[str] = mapped_column(String(20))
    payment_status: Mapped[str] = mapped_column(String(20), default='Pending')
    status: Mapped[str] = mapped_column(String(40), default='Placed')
    distance_km: Mapped[float] = mapped_column(Float)
    delivery_otp: Mapped[str] = mapped_column(String(4))
    otp_failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    otp_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    customer: Mapped['User'] = relationship(back_populates='orders')
    delivery_partner: Mapped['DeliveryPartner | None'] = relationship(back_populates='deliveries')
    items: Mapped[list['OrderItem']] = relationship(back_populates='order')
    history: Mapped[list['OrderStatusHistory']] = relationship(back_populates='order')

class OrderItem(TimestampMixin, Base):
    __tablename__ = 'order_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'))
    menu_item_id: Mapped[int] = mapped_column(ForeignKey('menu_items.id'))
    item_name: Mapped[str] = mapped_column(String(150))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10,2))
    packaging_charge: Mapped[Decimal] = mapped_column(Numeric(10,2), default=0)
    order: Mapped['Order'] = relationship(back_populates='items')

class CouponUsage(TimestampMixin, Base):
    __tablename__ = 'coupon_usages'
    __table_args__ = (UniqueConstraint('coupon_id', 'order_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey('coupons.id'))
    customer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'))
    coupon: Mapped['Coupon'] = relationship(back_populates='usages')

class DeliveryOffer(TimestampMixin, Base):
    __tablename__ = 'delivery_offers'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'))
    partner_id: Mapped[int] = mapped_column(ForeignKey('delivery_partners.id'))
    status: Mapped[str] = mapped_column(String(20), default='Pending')
    offered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Rating(TimestampMixin, Base):
    __tablename__ = 'ratings'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), unique=True)
    restaurant_rating: Mapped[int] = mapped_column(Integer)
    partner_rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)




class OrderStatusHistory(TimestampMixin, Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    old_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40))
    changed_by: Mapped[str] = mapped_column( String(50))

    # New Level 8 field
    reason: Mapped[str | None] = mapped_column(String(300),nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime,server_default=func.now())
    order: Mapped["Order"] = relationship(back_populates="history")


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"),nullable=False,index=True)
    title: Mapped[str] = mapped_column(String(150),nullable=False)
    message: Mapped[str] = mapped_column(Text,nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50),nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"),nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean,default=False,nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime,nullable=True)


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"),nullable=False,unique=True,index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"),nullable=False,index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2),nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30),nullable=False)
    provider: Mapped[str] = mapped_column(String(30),default="manual",nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(150),nullable=True,unique=True)
    status: Mapped[str] = mapped_column(String(30),default="Pending",nullable=False)

class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"),nullable=False,index=True)
    action: Mapped[str] = mapped_column(String(100),nullable=False)
    target_type: Mapped[str] = mapped_column(String(50),nullable=False)
    target_id: Mapped[int] = mapped_column( nullable=False)
    details: Mapped[str | None] = mapped_column(Text,nullable=True)
