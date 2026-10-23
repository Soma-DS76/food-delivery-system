from app.main import app
from app.routers.tracking import router as tracking_router


def test_required_http_api_paths_and_methods_are_registered():
    required = {
        ("POST", "/auth/register"),
        ("POST", "/auth/login"),
        ("GET", "/auth/me"),
        ("PUT", "/admin/users/{user_id}/approve"),
        ("POST", "/restaurants"),
        ("GET", "/restaurants/{restaurant_id}"),
        ("PUT", "/restaurants/{restaurant_id}"),
        ("PUT", "/restaurants/{restaurant_id}/open-status"),
        ("GET", "/restaurants/me"),
        ("POST", "/restaurants/{restaurant_id}/categories"),
        ("POST", "/restaurants/{restaurant_id}/menu-items"),
        ("GET", "/restaurants/{restaurant_id}/menu"),
        ("PUT", "/menu-items/{item_id}"),
        ("PUT", "/menu-items/{item_id}/availability"),
        ("DELETE", "/menu-items/{item_id}"),
        ("GET", "/restaurants/nearby"),
        ("POST", "/addresses"),
        ("GET", "/addresses"),
        ("PUT", "/addresses/{address_id}"),
        ("DELETE", "/addresses/{address_id}"),
        ("PUT", "/addresses/{address_id}/default"),
        ("GET", "/cart"),
        ("POST", "/cart/items"),
        ("PUT", "/cart/items/{item_id}"),
        ("DELETE", "/cart/items/{item_id}"),
        ("DELETE", "/cart"),
        ("POST", "/coupons"),
        ("GET", "/coupons"),
        ("PUT", "/coupons/{coupon_id}"),
        ("PUT", "/coupons/{coupon_id}/deactivate"),
        ("GET", "/coupons/available"),
        ("POST", "/cart/apply-coupon"),
        ("DELETE", "/cart/coupon"),
        ("POST", "/orders"),
        ("GET", "/orders"),
        ("GET", "/orders/{order_id}"),
        ("PUT", "/orders/{order_id}/cancel"),
        ("POST", "/orders/{order_id}/reorder"),
        ("GET", "/restaurants/me/orders"),
        ("PUT", "/orders/{order_id}/accept"),
        ("PUT", "/orders/{order_id}/reject"),
        ("PUT", "/orders/{order_id}/preparing"),
        ("PUT", "/orders/{order_id}/ready"),
        ("PUT", "/partners/me/availability"),
        ("PUT", "/partners/me/location"),
        ("GET", "/partners/me/offers"),
        ("PUT", "/offers/{offer_id}/accept"),
        ("PUT", "/offers/{offer_id}/decline"),
        ("PUT", "/orders/{order_id}/pickup"),
        ("PUT", "/orders/{order_id}/out-for-delivery"),
        ("PUT", "/orders/{order_id}/deliver"),
        ("GET", "/partners/me/earnings"),
        ("POST", "/orders/{order_id}/rating"),
        ("GET", "/restaurants/{restaurant_id}/ratings"),
        ("GET", "/reports/admin-dashboard"),
        ("GET", "/reports/top-restaurants"),
        ("GET", "/reports/coupon-usage"),
        ("GET", "/reports/restaurant-sales"),
        ("GET", "/reports/partner-summary"),
    }
    registered = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert required <= registered


def test_websocket_endpoints_match_the_specification():
    registered = {
        route.path for route in tracking_router.routes
        if type(route).__name__ == "APIWebSocketRoute"
    }
    assert {
        "/ws/orders/{order_id}",
        "/ws/restaurant",
        "/ws/partner",
    } <= registered


def test_mismatched_legacy_endpoint_paths_are_not_exposed():
    paths = app.openapi()["paths"]
    assert "/orders/checkout" not in paths
    assert "/restaurant-orders" not in paths
    assert "/admin/reports/summary" not in paths
