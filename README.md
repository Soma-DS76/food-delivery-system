# Food Delivery System API

A FastAPI backend for a food delivery workflow using MySQL, SQLAlchemy 2, Alembic, JWT access tokens, delivery-partner assignment, order tracking, notifications, and admin reports.

## Main application

The authoritative application is `app/`. Start it from the project root:

```bash
python -m venv venv
# Windows PowerShell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Set `DATABASE_URL` and a strong random `JWT_SECRET_KEY` in `.env` before running. Do not commit or share `.env`.

## Database migrations

After configuring the database:

```bash
alembic upgrade head
alembic current
```

Do not use `Base.metadata.create_all()` as a replacement for the versioned migrations in a deployed environment.

## API documentation

With the server running, open `http://127.0.0.1:8000/docs`.

The API uses the paths and HTTP methods from the requirements. In particular:

- Orders: `POST /orders`, `GET /orders`, `GET /orders/{order_id}`, `PUT /orders/{order_id}/cancel`, and `POST /orders/{order_id}/reorder`.
- Restaurant order handling: `GET /restaurants/me/orders` and `PUT /orders/{order_id}/accept|reject|preparing|ready`.
- Cart coupons: `POST /cart/apply-coupon`, `DELETE /cart/coupon`; coupon administration uses `PUT /coupons/{coupon_id}/deactivate` and `GET /coupons/available`.
- Ratings: `POST /orders/{order_id}/rating` and `GET /restaurants/{restaurant_id}/ratings`.
- Reports: `/reports/admin-dashboard`, `/reports/top-restaurants`, `/reports/coupon-usage`, `/reports/restaurant-sales`, and `/reports/partner-summary`.

The live tracking WebSockets are `/ws/orders/{order_id}`, `/ws/restaurant`, and `/ws/partner`.

## Checkout payment demo

Checkout accepts `payment_method` of `COD` or `ONLINE`:

- `COD`: payment status starts as `Pending` and is marked `Paid` when the order is delivered.
- `ONLINE`: a **mock** payment record is immediately marked `Paid`. This does not contact a real payment gateway.
- Online payment refunds are simulated by changing the local payment and order status to `Refunded` when an order is rejected.

Replace these mock transitions with verified provider webhooks and gateway refund APIs before production use.

## Background jobs

APScheduler starts with FastAPI and handles stale order rejection, offer expiration/retry, unassigned-order alerts, stale partner availability, and coupon expiry. Run a single app worker when using this in-process scheduler. Multiple workers need a dedicated scheduler process or distributed locking to avoid duplicate jobs.

## WebSocket test page

Open `websocket_test.html` in a browser and enter a valid access token. The customer tracking endpoint also supports the short-lived tracking-ticket flow exposed by `/orders/{order_id}/tracking-ticket`; restaurant and partner channels accept `?token=...`.

## Tests

```bash
python -m pytest -v
```

The tests in this repository cover selected helper logic and workflows. Add integration tests against a dedicated test database before deploying. Do not run destructive tests against production data.

## Notes

- `backend/` is an older/secondary implementation retained from the original archive. Run the root `app/` package with the command above.
- The scheduler and online payments are demo implementations, not production payment or distributed-job infrastructure.
