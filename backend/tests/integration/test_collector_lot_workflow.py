"""End-to-end integration tests for the collector-driven handover -> lot ->
bidding -> recycler-selection workflow (COLLECTOR PHONE requirements).

Unlike the RRR-centre-driven flow already covered by test_lots_api.py /
test_bids_api.py, none of this goes through an RRR_CENTER account: the
collector's own confirmed handover auto-drives the item straight to a
published, biddable lot (ewaste/service.py's auto_progress_to_listed_lot),
and the collector — not an RRR centre — is the one who later selects the
winning bid. Real HTTP calls through the FastAPI app throughout, no
service-layer shortcuts, so RBAC/ownership are exercised exactly as a real
client would hit them.
"""
import pytest


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _register_and_approve_recycler(client, seeded_admin, *, username, company_name):
    reg = await client.post(
        "/api/v1/recyclers/register",
        json={"username": username, "password": "recyclerpass1", "company_name": company_name},
    )
    assert reg.status_code == 200, reg.text
    user_id = reg.json()["user_id"]

    admin_token = await _login(client, "admin", "admin1234")
    approve = await client.post(
        f"/api/v1/admin/recyclers/{user_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200, approve.text
    return await _login(client, username, "recyclerpass1")


@pytest.fixture
async def handed_over_submission(client, seeded_admin, seeded_home_user, seeded_collector):
    """Drives one real submission through create -> handover via real HTTP
    calls (not direct service calls) since this test suite specifically
    exercises the handover route's auto-progression side effect. Returns
    (submission_id, collector_token, handover_response_json)."""
    home_token = await _login(client, "home-user-1", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    submit = await client.post(
        "/api/v1/ewaste/submissions",
        json={
            "ward_id": "WARD-1",
            "photo_file_id": "photo-1",
            "category": "Laptop",
            "condition": "Good",
            "approximate_weight_kg": 4.0,
            "home_lat": 12.9716,
            "home_lng": 77.5946,
        },
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "wf-submit-1"},
    )
    assert submit.status_code == 200, submit.text
    submission_id = submit.json()["submission_id"]

    handover = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={
            "photo_file_id": "handover-photo-1",
            "collector_lat": 12.97165,
            "collector_lng": 77.59465,
            "actual_weight_kg": 3.8,
        },
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "wf-handover-1"},
    )
    assert handover.status_code == 200, handover.text
    return submission_id, collector_token, handover.json()


@pytest.mark.asyncio
async def test_confirmed_handover_auto_publishes_a_lot(handed_over_submission):
    _submission_id, _collector_token, body = handed_over_submission
    assert body["status"] == "COLLECTED"
    assert body["verification_result"] == "VERIFIED"
    assert body["lot_id"] is not None
    assert body["lot_status"] == "LISTED_FOR_BIDDING"


@pytest.mark.asyncio
async def test_handed_over_item_leaves_pending_and_enters_accepted_collections(
    client, handed_over_submission
):
    submission_id, collector_token, _body = handed_over_submission
    headers = {"Authorization": f"Bearer {collector_token}"}

    pending = await client.get("/api/v1/ewaste/submissions/pending", headers=headers)
    assert pending.status_code == 200
    assert all(s["submission_id"] != submission_id for s in pending.json()["submissions"])

    accepted = await client.get("/api/v1/ewaste/submissions/handed-over", headers=headers)
    assert accepted.status_code == 200
    ids = [s["submission_id"] for s in accepted.json()["submissions"]]
    assert submission_id in ids


@pytest.mark.asyncio
async def test_collector_can_view_accepted_collection_detail(client, handed_over_submission):
    submission_id, collector_token, _body = handed_over_submission
    resp = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}",
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["category"] == "Laptop"
    assert detail["condition"] == "Good"
    assert detail["actual_weight_kg"] == 3.8
    assert detail["status"] == "LISTED_FOR_BIDDING"
    assert detail["lot_id"] is not None


@pytest.mark.asyncio
async def test_full_bidding_and_selection_workflow(client, seeded_admin, handed_over_submission):
    submission_id, collector_token, handover_body = handed_over_submission
    lot_id = handover_body["lot_id"]
    collector_headers = {"Authorization": f"Bearer {collector_token}"}

    recycler_a_token = await _register_and_approve_recycler(
        client, seeded_admin, username="recycler-a-wf", company_name="Recycler A"
    )
    recycler_b_token = await _register_and_approve_recycler(
        client, seeded_admin, username="recycler-b-wf", company_name="Recycler B"
    )

    # Steps 6/7: both recyclers see the same listed lot.
    for token in (recycler_a_token, recycler_b_token):
        listed = await client.get("/api/v1/lots/listed", headers={"Authorization": f"Bearer {token}"})
        assert listed.status_code == 200
        assert any(l["lot_id"] == lot_id for l in listed.json()["lots"])

    # Steps 8/9: both recyclers place a bid.
    bid_a = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": "500.00"},
        headers={"Authorization": f"Bearer {recycler_a_token}", "Idempotency-Key": "wf-bid-a"},
    )
    assert bid_a.status_code == 200, bid_a.text
    bid_a_id = bid_a.json()["bid_id"]

    bid_b = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": "550.00"},
        headers={"Authorization": f"Bearer {recycler_b_token}", "Idempotency-Key": "wf-bid-b"},
    )
    assert bid_b.status_code == 200, bid_b.text
    bid_b_id = bid_b.json()["bid_id"]

    # Step 10/11: collector retrieves bids for their lot and sees both.
    bids_resp = await client.get(f"/api/v1/lots/{lot_id}/bids", headers=collector_headers)
    assert bids_resp.status_code == 200, bids_resp.text
    bids = bids_resp.json()["bids"]
    assert len(bids) == 2
    assert {b["bid_id"] for b in bids} == {bid_a_id, bid_b_id}

    # Step 16a: an unrelated collector cannot see this lot's bids.
    from app.modules.collectors import service as collectors_service

    other = await collectors_service.create_collector(
        employee_id="EMP-OTHER",
        password="collectorpass1",
        ward_id="WARD-1",
        rrr_id=None,
        assigned_area_radius_m=None,
        actor={"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"},
    )
    other_token = await _login(client, "EMP-OTHER", "collectorpass1")
    forbidden_resp = await client.get(
        f"/api/v1/lots/{lot_id}/bids", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert forbidden_resp.status_code == 403
    assert forbidden_resp.json()["error_code"] == "NOT_LOT_OWNER"

    # Step 16b: a recycler cannot call the collector/RRR-only accept endpoint.
    recycler_forbidden = await client.post(
        f"/api/v1/bids/{bid_b_id}/accept",
        headers={"Authorization": f"Bearer {recycler_a_token}", "Idempotency-Key": "wf-bad-accept"},
    )
    assert recycler_forbidden.status_code == 403

    # Step 12: collector selects Recycler B.
    accept_resp = await client.post(
        f"/api/v1/bids/{bid_b_id}/accept",
        headers={**collector_headers, "Idempotency-Key": "wf-accept-b"},
    )
    assert accept_resp.status_code == 200, accept_resp.text
    assert accept_resp.json()["status"] == "ACCEPTED"

    # Step 15: a second selection attempt on the sibling bid cannot succeed —
    # it's no longer PLACED (implicitly rejected the moment B was accepted).
    second_attempt = await client.post(
        f"/api/v1/bids/{bid_a_id}/accept",
        headers={**collector_headers, "Idempotency-Key": "wf-accept-a-too-late"},
    )
    assert second_attempt.status_code == 400
    assert second_attempt.json()["error_code"] == "BID_NOT_ACCEPTABLE"

    # Steps 13/14: recycler-facing bid status is authoritative and persisted.
    mine_b = await client.get("/api/v1/bids/mine", headers={"Authorization": f"Bearer {recycler_b_token}"})
    assert mine_b.json()["bids"][0]["status"] == "ACCEPTED"

    mine_a = await client.get("/api/v1/bids/mine", headers={"Authorization": f"Bearer {recycler_a_token}"})
    assert mine_a.json()["bids"][0]["status"] == "REJECTED"

    # Step 17: notifications were created for both outcomes.
    notif_b = await client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {recycler_b_token}"}
    )
    assert notif_b.status_code == 200
    assert any(n["type"] == "BID_ACCEPTED" for n in notif_b.json()["notifications"])

    notif_a = await client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {recycler_a_token}"}
    )
    assert notif_a.status_code == 200
    assert any(n["type"] == "BID_REJECTED" for n in notif_a.json()["notifications"])

    # Submission id is unused beyond fixture setup verification above.
    assert submission_id
