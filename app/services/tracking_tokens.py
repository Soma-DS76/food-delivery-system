
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException


def secret_key():
    key = os.getenv("TRACKING_SECRET_KEY")

    if not key or len(key) < 32:
        raise RuntimeError( "Set TRACKING_SECRET_KEY to a random " "value of at least 32 characters")

    return key.encode("utf-8")


def encode_part(data: bytes):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def decode_part(value: str):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_tracking_ticket(order_id: int, customer_id: int):
    payload = { "order_id": order_id,"customer_id": customer_id,"exp": int(time.time()) + 60,}

    body = encode_part(json.dumps(payload, separators=(",", ":")).encode())

    signature = hmac.new(secret_key(),body.encode(),hashlib.sha256).digest()

    return f"{body}.{encode_part(signature)}"


def verify_tracking_ticket(ticket: str):
    try:
        body, signature = ticket.split(".")

        expected = hmac.new(secret_key(),body.encode(),hashlib.sha256).digest()

        if not hmac.compare_digest( expected,decode_part(signature)):
            raise ValueError("Invalid signature")

        payload = json.loads(decode_part(body))

        if (not isinstance(payload.get("order_id"), int)
            or not isinstance(payload.get("customer_id"), int)
            or not isinstance(payload.get("exp"), int)
            or payload["exp"] <= time.time()):
            raise ValueError("Invalid or expired ticket")

        return payload

    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException( status_code=401, detail="Invalid or expired tracking ticket", )
