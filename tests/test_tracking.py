
import pytest
from fastapi import HTTPException

from app.services.tracking_tokens import (
    create_tracking_ticket,
    verify_tracking_ticket,
)


@pytest.fixture(autouse=True)
def tracking_secret(monkeypatch):
    monkeypatch.setenv(
        "TRACKING_SECRET_KEY",
        "test-only-secret-key-12345678901234567890",
    )


def test_valid_ticket():
    ticket = create_tracking_ticket(10, 5)
    payload = verify_tracking_ticket(ticket)

    assert payload["order_id"] == 10
    assert payload["customer_id"] == 5


def test_invalid_ticket():
    with pytest.raises(HTTPException) as exc:
        verify_tracking_ticket("invalid.ticket")

    assert exc.value.status_code == 401


def test_modified_ticket():
    ticket = create_tracking_ticket(10, 5)
    body, signature = ticket.split(".")

    modified = body + "." + (
        ("A" if signature[0] != "A" else "B")
        + signature[1:]
    )

    with pytest.raises(HTTPException):
        verify_tracking_ticket(modified)
