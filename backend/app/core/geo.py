"""
Geo-tag verification primitives. Pure, dependency-free (stdlib `math` only)
so it can be unit-tested in isolation, same pattern as rbac_core.py.

Terminology note (Section 8 of the architecture doc): this is "geo-tag based
verification," never a claim that GPS can't be spoofed.
"""
import math

EARTH_RADIUS_METERS = 6371000.0


def haversine_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(min(1.0, a)))


def is_valid_coordinate(lat: float | None, lng: float | None) -> bool:
    """Rejects missing/null coordinates, out-of-range lat/lng, and the
    (0, 0) 'null island' sentinel some devices report on a GPS failure."""
    if lat is None or lng is None:
        return False
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return False
    if lat == 0.0 and lng == 0.0:
        return False
    return True
