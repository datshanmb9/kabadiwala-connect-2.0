"""GET /api/v1/pricing/trend — historical INR/kg from real accepted sales."""
from datetime import datetime, timedelta

import pytest
from bson import Decimal128
from decimal import Decimal

from app.db.mongo import get_db


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


_counter = 0


async def _sale(*, category, ward, weight, amount, days_ago, status="ACCEPTED"):
    """One lot plus one bid on it, exactly as the lots/bids modules store them."""
    global _counter
    _counter += 1
    lot_id = f"lot-{_counter}"
    accepted_at = (datetime.utcnow() - timedelta(days=days_ago)).replace(microsecond=0)
    await get_db().lots.insert_one(
        {"lot_id": lot_id, "category": category, "ward_id": ward, "total_weight_kg": weight, "status": "SOLD"}
    )
    await get_db().bids.insert_one(
        {
            "bid_id": f"bid-{_counter}",
            "lot_id": lot_id,
            "recycler_id": "r-1",
            "amount": Decimal128(Decimal(str(amount))),
            "status": status,
            "placed_at": accepted_at,
            "accepted_at": accepted_at if status in ("ACCEPTED", "CANCELLED") else None,
        }
    )


async def _trend(client, token, **params):
    resp = await client.get(
        "/api/v1/pricing/trend", params=params, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_no_history_returns_no_points_and_no_direction(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    body = await _trend(client, token, item="Laptop", ward_id="WARD-1")
    assert body["points"] == []
    assert body["trend"] == "insufficient_data"
    assert body["latest_price_per_kg"] is None
    assert body["source"] == "accepted_bids"


@pytest.mark.asyncio
async def test_ward_trend_is_chronological_filtered_and_increasing(client, seeded_home_user):
    # Laptop, WARD-1: 400 -> 420 -> 500 -> 520 INR/kg (amount / weight)
    await _sale(category="Laptop", ward="WARD-1", weight=2.0, amount=1000, days_ago=4)   # 500
    await _sale(category="Laptop", ward="WARD-1", weight=2.0, amount=800, days_ago=10)   # 400
    await _sale(category="laptop", ward="WARD-1", weight=1.0, amount=520, days_ago=1)    # 520 (case-insensitive)
    await _sale(category="Laptop", ward="WARD-1", weight=1.0, amount=420, days_ago=7)    # 420
    # Must be ignored: other item, other ward, not accepted, too old, no weight.
    await _sale(category="Smartphone", ward="WARD-1", weight=1.0, amount=9999, days_ago=2)
    await _sale(category="Laptop", ward="WARD-9", weight=1.0, amount=9999, days_ago=2)
    await _sale(category="Laptop", ward="WARD-1", weight=1.0, amount=9999, days_ago=2, status="PLACED")
    await _sale(category="Laptop", ward="WARD-1", weight=1.0, amount=9999, days_ago=2, status="REJECTED")
    await _sale(category="Laptop", ward="WARD-1", weight=1.0, amount=9999, days_ago=2, status="CANCELLED")
    await _sale(category="Laptop", ward="WARD-1", weight=1.0, amount=9999, days_ago=200)
    await _sale(category="Laptop", ward="WARD-1", weight=None, amount=9999, days_ago=2)

    token = await _login(client, "home-user-1", "homepass123")
    body = await _trend(client, token, item="Laptop", ward_id="WARD-1")

    assert body["scope"] == "ward"
    assert body["ward_id"] == "WARD-1"
    assert [p["price_per_kg"] for p in body["points"]] == [400.0, 420.0, 500.0, 520.0]
    assert body["points"] == sorted(body["points"], key=lambda p: p["date"])
    assert body["trend"] == "increasing"
    assert body["change_percent"] == 24.39  # (510 - 410) / 410
    assert body["latest_price_per_kg"] == 520.0
    assert body["latest_date"] == body["points"][-1]["date"]


@pytest.mark.asyncio
async def test_same_day_sales_are_averaged_into_one_point(client, seeded_home_user):
    await _sale(category="Router", ward="WARD-1", weight=1.0, amount=100, days_ago=3)
    await _sale(category="Router", ward="WARD-1", weight=1.0, amount=140, days_ago=3)
    token = await _login(client, "home-user-1", "homepass123")
    body = await _trend(client, token, item="Router", ward_id="WARD-1")
    assert len(body["points"]) == 1
    assert body["points"][0] == {**body["points"][0], "price_per_kg": 120.0, "sales": 2}
    assert body["trend"] == "insufficient_data"  # one day is not a trend


@pytest.mark.asyncio
async def test_detected_class_spelling_matches_stored_category(client, seeded_home_user):
    for days, amount in [(8, 100), (6, 100), (4, 100), (2, 101)]:
        await _sale(category="TV Remote Control", ward="WARD-1", weight=1.0, amount=amount, days_ago=days)
    token = await _login(client, "home-user-1", "homepass123")
    body = await _trend(client, token, item="TV-Remote-Control", ward_id="WARD-1")
    assert len(body["points"]) == 4
    assert body["trend"] == "stable"


@pytest.mark.asyncio
async def test_falls_back_to_all_wards_when_ward_has_too_little_data(client, seeded_collector):
    await _sale(category="Battery", ward="WARD-1", weight=1.0, amount=90, days_ago=1)
    for days, amount in [(9, 200), (7, 190), (5, 150)]:
        await _sale(category="Battery", ward="WARD-2", weight=1.0, amount=amount, days_ago=days)
    token = await _login(client, "EMP-001", "collectorpass1")  # collectors get the same data
    body = await _trend(client, token, item="Battery", ward_id="WARD-1")
    assert body["scope"] == "all_wards"
    assert body["ward_id"] is None
    assert [p["price_per_kg"] for p in body["points"]] == [200.0, 190.0, 150.0, 90.0]
    assert body["trend"] == "decreasing"
    assert body["latest_price_per_kg"] == 90.0


@pytest.mark.asyncio
async def test_home_user_and_collector_get_identical_results(client, seeded_home_user, seeded_collector):
    for days, amount in [(9, 300), (7, 310), (5, 305), (3, 312)]:
        await _sale(category="Mouse", ward="WARD-1", weight=1.0, amount=amount, days_ago=days)
    home = await _trend(client, await _login(client, "home-user-1", "homepass123"), item="Mouse", ward_id="WARD-1")
    collector = await _trend(client, await _login(client, "EMP-001", "collectorpass1"), item="Mouse", ward_id="WARD-1")
    assert home == collector


@pytest.mark.asyncio
async def test_trend_requires_home_user_or_collector_and_an_item(client, seeded_home_user):
    unauth = await client.get("/api/v1/pricing/trend", params={"item": "Laptop"})
    assert unauth.status_code == 401
    token = await _login(client, "home-user-1", "homepass123")
    missing = await client.get("/api/v1/pricing/trend", headers={"Authorization": f"Bearer {token}"})
    assert missing.status_code == 422
