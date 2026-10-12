"""Regression: the ML price estimate stored on a submission reaches the
collector's Pending Collections list and the recycler's Lot Detail with a
total range derived from the per-kg range and the weight, through the
unchanged submit -> handover -> auto-listed lot -> bid workflow."""
import pytest

from app.modules.pricing import service as pricing_service


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _approved_recycler_token(client):
    reg = await client.post(
        "/api/v1/recyclers/register",
        json={"username": "recycler-price", "password": "recyclerpass1", "company_name": "Price Recycler"},
    )
    assert reg.status_code == 200, reg.text
    admin_token = await _login(client, "admin", "admin1234")
    approve = await client.post(
        f"/api/v1/admin/recyclers/{reg.json()['user_id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200, approve.text
    return await _login(client, "recycler-price", "recyclerpass1")


async def _submit_with_backend_estimate(client, monkeypatch, weight_kg=0.40):
    # 109.12/kg -> +/-10% band -> 98.21 - 120.03 /kg
    monkeypatch.setattr(pricing_service, "predict_price", lambda **features: 109.12)
    home_token = await _login(client, "home-user-1", "homepass123")
    headers = {"Authorization": f"Bearer {home_token}"}

    estimate = await client.post(
        "/api/v1/pricing/estimate",
        json={
            "product_type": "e-waste-small-appliances",
            "condition": "Used",
            "total_weight_kg": weight_kg,
            "location": "WARD-1",
        },
        headers=headers,
    )
    assert estimate.status_code == 200, estimate.text
    submit = await client.post(
        "/api/v1/ewaste/submissions",
        json={
            "ward_id": "WARD-1",
            "photo_file_id": "photo-price",
            "category": "e-waste-small-appliances",
            "condition": "Used",
            "approximate_weight_kg": weight_kg,
            "price_estimate": estimate.json(),
            "home_lat": 12.9716,
            "home_lng": 77.5946,
        },
        headers={**headers, "Idempotency-Key": "price-flow-submit"},
    )
    assert submit.status_code == 200, submit.text
    return estimate.json(), submit.json()["submission_id"]


async def _handover(client, collector_token, submission_id, actual_weight_kg):
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={
            "photo_file_id": "handover-price",
            "collector_lat": 12.97165,
            "collector_lng": 77.59465,
            "actual_weight_kg": actual_weight_kg,
        },
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "price-flow-handover"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
async def handed_over_lot_id_without_estimate(client, seeded_home_user, seeded_collector):
    home_token = await _login(client, "home-user-1", "homepass123")
    submit = await client.post(
        "/api/v1/ewaste/submissions",
        json={
            "ward_id": "WARD-1",
            "photo_file_id": "p",
            "category": "Laptop",
            "home_lat": 12.9716,
            "home_lng": 77.5946,
        },
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "no-est-submit"},
    )
    assert submit.status_code == 200, submit.text
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    handover = await _handover(client, collector_token, submit.json()["submission_id"], actual_weight_kg=1.0)
    return handover["lot_id"]


@pytest.mark.asyncio
async def test_estimate_endpoint_returns_total_range(client, seeded_home_user, monkeypatch):
    estimate, _ = await _submit_with_backend_estimate(client, monkeypatch)

    assert (estimate["min_price"], estimate["max_price"]) == (98.21, 120.03)
    assert estimate["weight_kg"] == 0.40
    assert (estimate["estimated_total_min"], estimate["estimated_total_max"]) == (39.28, 48.01)


@pytest.mark.asyncio
async def test_pending_collections_include_stored_estimate_with_total_range(
    client, seeded_home_user, seeded_collector, monkeypatch
):
    _, submission_id = await _submit_with_backend_estimate(client, monkeypatch)
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    pending = await client.get(
        "/api/v1/ewaste/submissions/pending", headers={"Authorization": f"Bearer {collector_token}"}
    )

    assert pending.status_code == 200, pending.text
    item = next(s for s in pending.json()["submissions"] if s["submission_id"] == submission_id)
    est = item["price_estimate"]
    assert (est["min_price"], est["max_price"]) == (98.21, 120.03)
    assert est["weight_kg"] == 0.40
    assert (est["estimated_total_min"], est["estimated_total_max"]) == (39.28, 48.01)


@pytest.mark.asyncio
async def test_pending_collections_backfill_totals_for_older_stored_estimates(
    client, seeded_home_user, seeded_collector
):
    from app.db.mongo import get_db

    home_token = await _login(client, "home-user-1", "homepass123")
    submit = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "p", "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "legacy-submit"},
    )
    submission_id = submit.json()["submission_id"]
    # An estimate stored before the total-range fields existed.
    legacy_estimate = {
        "predicted_price_per_kg": 109.12,
        "min_price": 98.21,
        "max_price": 120.03,
        "estimated_total_value": 43.65,
        "product_type": "e-waste-small-appliances",
        "condition": "Used",
        "weight_kg": 0.40,
        "is_estimate": True,
        "estimated_at": "2026-09-01T00:00:00Z",
    }
    await get_db().e_waste_submissions.update_one(
        {"submission_id": submission_id}, {"$set": {"price_estimate": legacy_estimate}}
    )
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    pending = await client.get(
        "/api/v1/ewaste/submissions/pending", headers={"Authorization": f"Bearer {collector_token}"}
    )

    item = next(s for s in pending.json()["submissions"] if s["submission_id"] == submission_id)
    est = item["price_estimate"]
    assert (est["estimated_total_min"], est["estimated_total_max"]) == (39.28, 48.01)


@pytest.mark.asyncio
async def test_recycler_lot_detail_shows_same_estimate_and_bidding_still_works(
    client, seeded_admin, seeded_home_user, seeded_collector, monkeypatch
):
    _, submission_id = await _submit_with_backend_estimate(client, monkeypatch)
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    handover = await _handover(client, collector_token, submission_id, actual_weight_kg=0.40)
    assert handover["lot_status"] == "LISTED_FOR_BIDDING"
    lot_id = handover["lot_id"]

    recycler_token = await _approved_recycler_token(client)
    recycler_headers = {"Authorization": f"Bearer {recycler_token}"}
    lot = await client.get(f"/api/v1/lots/{lot_id}", headers=recycler_headers)

    assert lot.status_code == 200, lot.text
    body = lot.json()
    assert body["status"] == "LISTED_FOR_BIDDING"
    est = body["price_estimate"]
    assert (est["min_price"], est["max_price"]) == (98.21, 120.03)
    assert est["weight_kg"] == 0.40
    assert (est["estimated_total_min"], est["estimated_total_max"]) == (39.28, 48.01)

    bid = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": "45.00"},
        headers={**recycler_headers, "Idempotency-Key": "price-flow-bid"},
    )
    assert bid.status_code == 200, bid.text


@pytest.mark.asyncio
async def test_lot_estimate_total_uses_actual_collected_weight(
    client, seeded_admin, seeded_home_user, seeded_collector, monkeypatch
):
    _, submission_id = await _submit_with_backend_estimate(client, monkeypatch, weight_kg=0.40)
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    handover = await _handover(client, collector_token, submission_id, actual_weight_kg=0.10)

    recycler_token = await _approved_recycler_token(client)
    lot = await client.get(
        f"/api/v1/lots/{handover['lot_id']}", headers={"Authorization": f"Bearer {recycler_token}"}
    )

    body = lot.json()
    assert body["total_weight_kg"] == 0.10
    est = body["price_estimate"]
    assert (est["min_price"], est["max_price"]) == (98.21, 120.03)
    assert est["weight_kg"] == 0.10
    assert (est["estimated_total_min"], est["estimated_total_max"]) == (9.82, 12.0)


@pytest.mark.asyncio
async def test_lot_without_stored_estimate_has_no_price_estimate(
    client, seeded_admin, handed_over_lot_id_without_estimate
):
    recycler_token = await _approved_recycler_token(client)
    lot = await client.get(
        f"/api/v1/lots/{handed_over_lot_id_without_estimate}",
        headers={"Authorization": f"Bearer {recycler_token}"},
    )

    assert lot.status_code == 200, lot.text
    assert lot.json()["price_estimate"] is None
