from datetime import date, datetime

from app.modules.pricing import service


def _points(prices):
    return [{"date": date(2026, 9, day + 1), "price_per_kg": p, "sales": 1} for day, p in enumerate(prices)]


def test_normalize_item_matches_detected_and_typed_names():
    assert service.normalize_item("TV-Remote-Control") == "tv remote control"
    assert service.normalize_item("  tv remote   control ") == "tv remote control"
    assert service.normalize_item("Laptop") == service.normalize_item("laptop")


def test_daily_points_are_chronological_daily_means():
    obs = [
        (datetime(2026, 9, 3, 15), 120.0),
        (datetime(2026, 9, 1, 9), 100.0),
        (datetime(2026, 9, 3, 9), 110.0),
    ]
    points = service.daily_price_points(obs)
    assert [p["date"] for p in points] == [date(2026, 9, 1), date(2026, 9, 3)]
    assert [p["price_per_kg"] for p in points] == [100.0, 115.0]
    assert [p["sales"] for p in points] == [1, 2]


def test_increasing_trend():
    # earlier avg 101, recent avg 120 -> +18.81%
    assert service.trend_direction(_points([100, 102, 118, 122])) == ("increasing", 18.81)


def test_decreasing_trend():
    assert service.trend_direction(_points([200, 190, 150, 150])) == ("decreasing", -23.08)


def test_small_fluctuation_is_stable():
    trend, change = service.trend_direction(_points([100, 103, 99, 104]))
    assert trend == "stable"
    assert abs(change) < service.STABLE_THRESHOLD_PERCENT


def test_odd_count_leaves_middle_point_out():
    trend, change = service.trend_direction(_points([100, 100, 500, 110, 110]))
    assert (trend, change) == ("increasing", 10.0)


def test_too_few_points_claims_no_direction():
    assert service.trend_direction(_points([100, 200, 300])) == ("insufficient_data", None)
    assert service.trend_direction([]) == ("insufficient_data", None)
