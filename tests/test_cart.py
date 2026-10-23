
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.cart import ( AddCartItemRequest, UpdateCartItemRequest )
from app.routers.cart import ( money,calculate_line_total,build_cart_response )


def test_valid_quantity():
    data = AddCartItemRequest( menu_item_id=1, quantity=3 )

    assert data.quantity == 3


def test_quantity_zero_rejected():
    with pytest.raises(ValidationError):
        AddCartItemRequest( menu_item_id=1, quantity=0 )


def test_quantity_above_ten_rejected():
    with pytest.raises(ValidationError):
        AddCartItemRequest( menu_item_id=1, quantity=11 )


def test_update_quantity_validation():
    with pytest.raises(ValidationError):
        UpdateCartItemRequest(quantity=0)


def test_line_total():
    result = calculate_line_total(
        Decimal("249.00"),
        2
    )

    assert result == Decimal("498.00")


def test_money_precision():
    assert money("10.50") == Decimal("10.50")


def test_empty_cart():
    result = build_cart_response(None, None)

    assert result["items"] == []
    assert result["restaurant_id"] is None
    assert result["grand_total"] == Decimal("0.00")
