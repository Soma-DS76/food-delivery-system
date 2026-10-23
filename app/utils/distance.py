
from math import radians, sin, cos, sqrt, atan2

EARTH_RADIUS_KM = 6371.0088
AVERAGE_SPEED_KMH = 20


def haversine_distance( lat1: float, lon1: float, lat2: float, lon2: float ) -> float:
    """Calculate great-circle distance in kilometers."""

    lat1, lon1, lat2, lon2 = map( radians, [lat1, lon1, lat2, lon2] )

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = ( sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2 )

    a = min(1.0, max(0.0, a))

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def estimated_delivery_minutes( distance_km: float, preparation_minutes: int ) -> int:
    """Preparation time plus estimated travel time."""

    from math import ceil

    travel_minutes = ( distance_km / AVERAGE_SPEED_KMH ) * 60

    return ceil(preparation_minutes + travel_minutes)
