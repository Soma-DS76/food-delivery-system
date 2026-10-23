
import pytest
from app.utils.distance import ( haversine_distance,estimated_delivery_minutes )


def test_same_location():
    distance = haversine_distance( 12.9569, 77.7011, 12.9569, 77.7011)

    assert distance == pytest.approx(0)


def test_distance_is_symmetric():
    first = haversine_distance( 12.9569, 77.7011, 12.9716, 77.5946 )

    second = haversine_distance( 12.9716, 77.5946, 12.9569, 77.7011 )

    assert first == pytest.approx(second)


def test_known_distance():
    # Equatorial longitude difference of one degree.
    distance = haversine_distance( 0, 0, 0, 1 )

    assert distance == pytest.approx( 111.195, abs=0.01 )


def test_estimated_delivery():
    assert estimated_delivery_minutes( distance_km=4, preparation_minutes=30 ) == 42


def test_zero_distance_eta():
    assert estimated_delivery_minutes( distance_km=0, preparation_minutes=25 ) == 25
