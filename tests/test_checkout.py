
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.order import CheckoutRequest
from app.services.checkout import (
    calculate_order_total,
    calculate_delivery_fee,
    create_order_number,
    money
)


def test_checkout_request():
    data = CheckoutRequest(
        address_id=1,
        payment_method="COD",
        tip_amount="20.00"
    )

    assert data.address_id == 1
    assert data.payment_method == "COD"


def test_invalid_address():
    with pytest.raises(ValidationError):
        CheckoutRequest(address_id=0)


def test_negative_tip():
    with pytest.raises(ValidationError):
        CheckoutRequest(
            address_id=1,
            tip_amount="-10"
        )


def test_online_payment_method_is_supported():
    data = CheckoutRequest(address_id=1, payment_method="ONLINE")
    assert data.payment_method == "ONLINE"


def test_unsupported_payment_method():
    with pytest.raises(ValidationError):
        CheckoutRequest(address_id=1, payment_method="CRYPTO")


def test_total_without_coupon():
    total = calculate_order_total(
        item_total="500",
        discount="0",
        packaging="20",
        delivery_fee="30",
        platform_fee="5",
        gst="0",
        tip="0"
    )

    assert total == Decimal("555.00")


def test_total_with_coupon():
    total = calculate_order_total(
        item_total="500",
        discount="100",
        packaging="20",
        delivery_fee="30",
        platform_fee="5",
        gst="0",
        tip="0"
    )

    assert total == Decimal("455.00")


def test_total_with_tip():
    total = calculate_order_total(
        item_total="500",
        discount="100",
        packaging="20",
        delivery_fee="30",
        platform_fee="5",
        gst="0",
        tip="25"
    )

    assert total == Decimal("480.00")


def test_discount_cannot_exceed_subtotal():
    with pytest.raises(ValueError):
        calculate_order_total(
            item_total="100",
            discount="200",
            packaging="0",
            delivery_fee="30",
            platform_fee="5",
            gst="0",
            tip="0"
        )


def test_money_rounding():
    assert money("99.999") == Decimal("100.00")


@pytest.mark.parametrize(
    ("distance_km", "expected"),
    [(0, "20.00"), (3, "20.00"), (3.1, "28.00"), (5, "36.00")],
)
def test_delivery_fee_matches_distance_formula(distance_km, expected):
    assert calculate_delivery_fee(distance_km) == Decimal(expected)


def test_unique_order_numbers():
    first = create_order_number()
    second = create_order_number()

    assert first.startswith("FD-")
    assert second.startswith("FD-")
    assert first != second
