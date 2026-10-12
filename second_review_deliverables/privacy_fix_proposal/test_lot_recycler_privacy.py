"""Regression tests: recyclers must never receive household-identifying or
household-locating data through lot responses (architecture Section 17,
"Household privacy leakage to RRR/recycler").

A lot's stored item_details hold the home user's ID, the collector's ID and
the GPS point / timestamp / photo recorded at the handover (which is taken
within MAX_HANDOVER_DISTANCE_METERS of the household). Lot owners (the RRR
centre or the collector of an auto-created lot) and the Government Admin
legitimately need that evidence; recyclers only need what they are bidding
on (category, weights, deadline, price estimate).
"""
import pytest

from tests.integration.test_collector_lot_workflow import (  # noqa: F401  (fixture import)
    _login,
    _register_and_approve_recycler,
    handed_over_submission,
)

HIDDEN_FROM_RECYCLER = {
    "home_user_id",
    "collector_id",
    "collector_lat",
    "collector_lng",
    "collection_ts",
    "collection_photo_file_id",
}


def _assert_no_hidden_fields(item_details):
    assert item_details, "expected at least one item record"
    for item in item_details:
        leaked = HIDDEN_FROM_RECYCLER & set(item)
        assert not leaked, f"recycler response leaked {sorted(leaked)}"


@pytest.mark.asyncio
async def test_recycler_listed_lots_hide_household_fields(client, seeded_admin, handed_over_submission):
    _submission_id, _collector_token, body = handed_over_submission
    token = await _register_and_approve_recycler(client, seeded_admin, username="priv-rcy-1", company_name="Privacy A")

    resp = await client.get("/api/v1/lots/listed", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    lot = next(l for l in resp.json()["lots"] if l["lot_id"] == body["lot_id"])
    _assert_no_hidden_fields(lot["item_details"])


@pytest.mark.asyncio
async def test_recycler_lot_detail_hides_household_fields_but_keeps_weight(
    client, seeded_admin, handed_over_submission
):
    submission_id, _collector_token, body = handed_over_submission
    token = await _register_and_approve_recycler(client, seeded_admin, username="priv-rcy-2", company_name="Privacy B")

    resp = await client.get(f"/api/v1/lots/{body['lot_id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    lot = resp.json()
    _assert_no_hidden_fields(lot["item_details"])
    # What a recycler legitimately needs to bid is still there.
    assert lot["item_details"][0]["submission_id"] == submission_id
    assert lot["item_details"][0]["actual_weight_kg"] == 3.8
    assert lot["total_weight_kg"] == 3.8
    assert lot["category"] == "Laptop"


@pytest.mark.asyncio
async def test_collector_lot_owner_still_sees_handover_evidence(client, handed_over_submission):
    _submission_id, collector_token, body = handed_over_submission
    resp = await client.get(f"/api/v1/lots/{body['lot_id']}", headers={"Authorization": f"Bearer {collector_token}"})
    assert resp.status_code == 200, resp.text
    item = resp.json()["item_details"][0]
    assert item["collector_lat"] == 12.97165
    assert item["collector_lng"] == 77.59465
    assert item["home_user_id"]


@pytest.mark.asyncio
async def test_admin_still_sees_full_item_details(client, seeded_admin, handed_over_submission):
    _submission_id, _collector_token, body = handed_over_submission
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get(f"/api/v1/lots/{body['lot_id']}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    item = resp.json()["item_details"][0]
    assert {"home_user_id", "collector_lat", "collector_lng"} <= set(item)
