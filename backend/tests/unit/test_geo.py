"""
Pure stdlib-only tests for app.core.geo — no FastAPI/Mongo dependency.
"""
from app.core.geo import haversine_distance_meters, is_valid_coordinate


def test_haversine_zero_distance_for_identical_points():
    assert haversine_distance_meters(12.9716, 77.5946, 12.9716, 77.5946) == 0.0


def test_haversine_known_short_distance_within_tolerance():
    # ~15m apart (small lat/lng offset near Bangalore).
    d = haversine_distance_meters(12.9716, 77.5946, 12.97174, 77.59474)
    assert 0 < d < 30


def test_haversine_known_long_distance_bangalore_to_chennai():
    # Bangalore to Chennai is roughly 290km; assert it's clearly far, not exact.
    d = haversine_distance_meters(12.9716, 77.5946, 13.0827, 80.2707)
    assert 250_000 < d < 320_000


def test_valid_coordinate_accepts_normal_values():
    assert is_valid_coordinate(12.9716, 77.5946) is True


def test_valid_coordinate_rejects_none():
    assert is_valid_coordinate(None, 77.5946) is False
    assert is_valid_coordinate(12.9716, None) is False
    assert is_valid_coordinate(None, None) is False


def test_valid_coordinate_rejects_out_of_range():
    assert is_valid_coordinate(91.0, 77.5946) is False
    assert is_valid_coordinate(12.9716, 181.0) is False
    assert is_valid_coordinate(-91.0, 0.0) is False


def test_valid_coordinate_rejects_null_island_sentinel():
    assert is_valid_coordinate(0.0, 0.0) is False
