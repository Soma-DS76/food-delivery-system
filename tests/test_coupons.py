
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.coupon import CouponCreate
from app.services.coupons import (
    calculate_discount,
    money
)


def sample_coupon(
    discount_type,
    discount_value,
    max_discount=None
):
    return SimpleNamespace(
        discount_type=discount_type,
        discount_value=Decimal(discount_value),
        max_discount=(
            Decimal(max_discount)
            if max_discount is not None
            else None
        )
    )


def test_percentage_discount():
    coupon = sample_coupon(
        "percentage", "20"
    )

    assert calculate_discount(
        coupon, Decimal("500")
    ) == Decimal("100.00")


def test_flat_discount():
    coupon = sample_coupon(
        "flat", "75"
    )

    assert calculate_discount(
        coupon, Decimal("500")
    ) == Decimal("75.00")


def test_maximum_discount_cap():
    coupon = sample_coupon(
        "percentage", "50", "100"
    )

    assert calculate_discount(
        coupon, Decimal("500")
    ) == Decimal("100.00")


def test_discount_cannot_exceed_subtotal():
    coupon = sample_coupon(
        "flat", "500"
    )

    assert calculate_discount(
        coupon, Decimal("200")
    ) == Decimal("200.00")


def test_rounding():
    assert money("10.555") == Decimal("10.56")


def test_invalid_percentage():
    now = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    with pytest.raises(ValidationError):
        CouponCreate(
            code="BAD150",
            discount_type="percentage",
            discount_value="150",
            valid_from=now,
            valid_to=now + timedelta(days=7)
        )


def test_invalid_date_range():
    now = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    with pytest.raises(ValidationError):
        CouponCreate(
            code="INVALIDDATE",
            discount_type="flat",
            discount_value="50",
            valid_from=now,
            valid_to=now
        )
