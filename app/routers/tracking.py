
from fastapi import (APIRouter, Depends, HTTPException,WebSocket, WebSocketDisconnect)
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.auth.security import require_roles
from app.models.entities import Order, User
from app.services.tracking import tracking_manager
from app.services.tracking_tokens import (create_tracking_ticket,verify_tracking_ticket)


router = APIRouter(tags=[" Live Tracking"])


@router.post("/orders/{order_id}/tracking-ticket")
def get_tracking_ticket(order_id: int,db: Session = Depends(get_db),user: User = Depends(require_roles("customer"))):
    order = db.get(Order, order_id)

    if not order or order.customer_id != user.id:
        raise HTTPException(404, "Order not found")

    ticket = create_tracking_ticket(order.id, user.id)

    return {"ticket": ticket,"expires_in_seconds": 60, "websocket_path": f"/ws/orders/{order_id}"}


@router.websocket("/ws/orders/{order_id}")
async def track_order(websocket: WebSocket, order_id: int, token: str | None = None):
    # Receive the ticket in the first WebSocket message
    # rather than putting it in the URL.
    await websocket.accept()

    try:
        if token:
            identity = await _authenticate_websocket_token(token)
            if identity is None or identity["role"] != "customer":
                await websocket.close(code=1008)
                return
            customer_id = identity["id"]
        else:
            # Backwards-compatible short-lived ticket handshake.
            ticket = await websocket.receive_text()
            payload = verify_tracking_ticket(ticket)
            if payload["order_id"] != order_id:
                await websocket.close(code=1008)
                return
            customer_id = payload["customer_id"]

        with SessionLocal() as db:
            order = db.get(Order, order_id)
            if not order or order.customer_id != customer_id:
                await websocket.close(code=1008)
                return
            status = order.status
            partner_id = order.delivery_partner_id

        # Connection was already accepted above.
        await tracking_manager.register(order_id, websocket)

        await websocket.send_json({ "type": "connected","order_id": order_id,"status": status,
                                   "delivery_partner_assigned": partner_id is not None})

        # Poll the database so status and partner-location changes are pushed
        # even when the client does not send heartbeat messages.
        last_status = status
        last_partner_id = partner_id
        last_location = None
        while True:
            try:
                await __import__("asyncio").wait_for(websocket.receive_text(), timeout=2.0)
            except __import__("asyncio").TimeoutError:
                pass
            with SessionLocal() as db:
                current = db.get(Order, order_id)
                if current is None or current.customer_id != customer_id:
                    await websocket.close(code=1008)
                    return
                if current.status != last_status:
                    last_status = current.status
                    await websocket.send_json({"type": "status_update", "order_id": order_id,
                                               "status": last_status})
                current_partner_id = current.delivery_partner_id
                if current_partner_id != last_partner_id:
                    last_partner_id = current_partner_id
                    await websocket.send_json({"type": "partner_assignment", "order_id": order_id,
                                               "delivery_partner_assigned": current_partner_id is not None})
                if current_partner_id is not None:
                    from app.models.entities import DeliveryPartner
                    partner = db.get(DeliveryPartner, current_partner_id)
                    location = ((partner.current_latitude, partner.current_longitude, partner.last_location_at.isoformat() if partner and partner.last_location_at else None)
                                if partner else None)
                    if location and location != last_location and location[0] is not None and location[1] is not None:
                        last_location = location
                        await websocket.send_json({"type": "location_update", "order_id": order_id,
                                                   "latitude": location[0], "longitude": location[1],
                                                   "updated_at": location[2]})

    except WebSocketDisconnect:
        pass

    except HTTPException:
        await websocket.close(code=1008)

    finally:
        await tracking_manager.disconnect(order_id, websocket)


async def _authenticate_websocket_token(token: str | None):
    """Validate the same 30-minute access token used by HTTP endpoints."""
    import jwt
    from app.auth.security import SECRET_KEY, ALGORITHM
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        user_id = int(payload.get("sub"))
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return None
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return {"id": user.id, "role": user.role, "approved": user.is_approved}


@router.websocket("/ws/restaurant")
async def restaurant_order_stream(websocket: WebSocket, token: str | None = None):
    """Restaurant-owner stream; sends a current snapshot on connect."""
    identity = await _authenticate_websocket_token(token)
    if identity is None or identity["role"] != "restaurant_owner" or not identity["approved"]:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        with SessionLocal() as db:
            from sqlalchemy import select
            from app.models.entities import Restaurant, Order
            restaurant_ids = select(Restaurant.id).where(Restaurant.owner_id == identity["id"])
            orders = db.scalars(select(Order).where(Order.restaurant_id.in_(restaurant_ids),
                                                    Order.status.in_(["Placed", "Accepted", "Preparing", "ReadyForPickup"]))
                                .order_by(Order.placed_at.desc()).limit(100)).all()
            snapshot = [{"order_id": o.id, "order_number": o.order_number,
                         "status": o.status, "restaurant_id": o.restaurant_id,
                         "created_at": o.placed_at.isoformat() if o.placed_at else None}
                        for o in orders]
        await websocket.send_json({"type": "restaurant_snapshot", "orders": snapshot})
        last_snapshot = snapshot
        import asyncio
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
            with SessionLocal() as db:
                from sqlalchemy import select
                from app.models.entities import Restaurant, Order
                restaurant_ids = select(Restaurant.id).where(Restaurant.owner_id == identity["id"])
                orders = db.scalars(select(Order).where(Order.restaurant_id.in_(restaurant_ids),
                                                        Order.status.in_(["Placed", "Accepted", "Preparing", "ReadyForPickup"]))
                                    .order_by(Order.placed_at.desc()).limit(100)).all()
                snapshot = [{"order_id": o.id, "order_number": o.order_number,
                             "status": o.status, "restaurant_id": o.restaurant_id,
                             "created_at": o.placed_at.isoformat() if o.placed_at else None}
                            for o in orders]
            if snapshot != last_snapshot:
                await websocket.send_json({"type": "restaurant_orders_update", "orders": snapshot})
                last_snapshot = snapshot
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/partner")
async def partner_offer_stream(websocket: WebSocket, token: str | None = None):
    """Delivery-partner stream; sends current pending offers on connect."""
    identity = await _authenticate_websocket_token(token)
    if identity is None or identity["role"] != "delivery_partner" or not identity["approved"]:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        with SessionLocal() as db:
            from sqlalchemy import select
            from app.models.entities import DeliveryPartner, DeliveryOffer
            partner = db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == identity["id"]))
            if partner is None or not partner.is_approved:
                await websocket.close(code=1008)
                return
            offers = db.scalars(select(DeliveryOffer).where(
                DeliveryOffer.partner_id == partner.id,
                DeliveryOffer.status == "Pending",
                DeliveryOffer.expires_at > __import__("datetime").datetime.utcnow(),
            ).order_by(DeliveryOffer.offered_at.desc())).all()
            snapshot = [{"offer_id": o.id, "order_id": o.order_id,
                         "expires_at": o.expires_at.isoformat()} for o in offers]
        await websocket.send_json({"type": "partner_offer_snapshot", "offers": snapshot})
        last_snapshot = snapshot
        import asyncio
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
            with SessionLocal() as db:
                from sqlalchemy import select
                from app.models.entities import DeliveryPartner, DeliveryOffer
                partner = db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == identity["id"]))
                offers = db.scalars(select(DeliveryOffer).where(
                    DeliveryOffer.partner_id == partner.id,
                    DeliveryOffer.status == "Pending",
                    DeliveryOffer.expires_at > __import__("datetime").datetime.utcnow(),
                ).order_by(DeliveryOffer.offered_at.desc())).all()
                snapshot = [{"offer_id": o.id, "order_id": o.order_id,
                             "expires_at": o.expires_at.isoformat()} for o in offers]
            if snapshot != last_snapshot:
                await websocket.send_json({"type": "partner_offers_update", "offers": snapshot})
                last_snapshot = snapshot
    except WebSocketDisconnect:
        pass
