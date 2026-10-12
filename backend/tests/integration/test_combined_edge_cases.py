"""
Phase 10: edge cases that only exist at the INTERSECTION of two or more
modules — each individual module's own failure mode (disabled account,
payment failure, duplicate idempotency key, complaint filing) already
has a dedicated test in its own phase's suite. These tests combine two
such cases in the same flow to catch interaction bugs a single-module
test can't see by construction.
"""
import pytest

from app.db.mongo import get_db


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_disabling_a_collector_mid_session_blocks_their_next_handover_immediately(
    client, seeded_admin, seeded_collector, seeded_home_user
):
    """Crosses the Phase 7 admin-collector-status module with the Phase 2
    ewaste-handover module: a token issued BEFORE the account was
    disabled must still be rejected on the very next request, since
    get_current_user() re-checks status from the database every time —
    not just at login."""
    home_token = await _login(client, "home-user-1", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")  # issued while still ACTIVE

    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "p", "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "combo-disable-submit"},
    )
    submission_id = submit_resp.json()["submission_id"]

    admin_token = await _login(client, "admin", "admin1234")
    disable_resp = await client.post(
        f"/api/v1/admin/collectors/{seeded_collector['user_id']}/status",
        json={"status": "DISABLED"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert disable_resp.json()["collector"]["status"] == "DISABLED"

    # The collector's ALREADY-ISSUED token is used again — never re-logged in.
    handover_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p", "collector_lat": 12.97165, "collector_lng": 77.59465},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "combo-disable-handover"},
    )
    assert handover_resp.status_code == 403
    assert handover_resp.json()["error_code"] == "ACCOUNT_DISABLED"

    # Re-enabling restores real API access immediately, same live re-check.
    await client.post(
        f"/api/v1/admin/collectors/{seeded_collector['user_id']}/status",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    retry_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p", "collector_lat": 12.97165, "collector_lng": 77.59465},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "combo-disable-handover-2"},
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "COLLECTED"


@pytest.mark.asyncio
async def test_reward_already_computed_is_never_clawed_back_when_the_sale_later_fails(
    client, seeded_admin, seeded_collector, seeded_rrr_center, seeded_approved_recycler, seeded_ward
):
    """Crosses the Phase 9 rewards module with the Phase 9 payments module:
    a reward is computed for an item while its lot is still mid-workflow
    (long before any payment attempt), the sale's payment then genuinely
    FAILS, and the reward must be completely unaffected — proving reward
    eligibility and marketplace/payment outcome are truly independent
    systems, not just independent in the common successful case."""
    from app.modules.ewaste import service as ewaste_service
    from app.modules.home_users import service as home_users_service
    from app.modules.lots import service as lots_service

    home_result = await home_users_service.register(
        username="combo-reward-home", password="homepass123", full_name="Combo", address="x",
        ward_id="WARD-1", household_lat=12.9716, household_lng=77.5946, upi_id="combo-reward-home@upi",
    )
    submit_result = await ewaste_service.create_submission(
        current_user=home_result["user"], ward_id="WARD-1", photo_file_id="p",
        home_lat=12.9716, home_lng=77.5946, home_ts=None, idempotency_key="combo-reward-submit",
    )
    submission_id = submit_result["submission_id"]
    handover_result = await ewaste_service.handover(
        current_user=seeded_collector, submission_id=submission_id, photo_file_id="p",
        collector_lat=12.97165, collector_lng=77.59465, collector_ts=None, idempotency_key="combo-reward-handover",
    )
    assert handover_result["status"] == "COLLECTED"

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")

    # Compute the reward NOW — the item hasn't even reached AT_RRR yet.
    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    created = [r for r in compute_resp.json()["created"] if r["home_user_id"] == home_result["user"]["user_id"]]
    assert len(created) == 1
    reward_id = created[0]["reward_id"]
    original_amount = created[0]["amount"]

    # Now drive the SAME item all the way through to a FAILED payment.
    await ewaste_service.receive(current_user=seeded_rrr_center, submission_id=submission_id, idempotency_key="combo-reward-receive")
    await ewaste_service.classify(
        current_user=seeded_rrr_center, submission_id=submission_id, category="metal-scrap", idempotency_key="combo-reward-classify",
    )
    lot_result = await lots_service.create_lot(
        current_user=seeded_rrr_center, category="metal-scrap", submission_ids=[submission_id], idempotency_key="combo-reward-lotcreate",
    )
    lot_id = lot_result["lot_id"]
    await lots_service.publish_lot(current_user=seeded_rrr_center, lot_id=lot_id, idempotency_key="combo-reward-publish")

    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    bid_resp = await client.post(
        "/api/v1/bids", json={"lot_id": lot_id, "amount": "100.00"},  # "100.00" is a known deterministic FAILURE
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "combo-reward-bid"},
    )
    bid_id = bid_resp.json()["bid_id"]
    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    await client.post(f"/api/v1/bids/{bid_id}/accept", headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "combo-reward-accept"})
    book_resp = await client.post(
        f"/api/v1/logistics/{lot_id}/book", json={"slot_time": "2026-11-02T10:00:00Z"},
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "combo-reward-book"},
    )
    booking_id = book_resp.json()["booking_id"]
    await client.post(
        f"/api/v1/logistics/{booking_id}/confirm-collection",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "combo-reward-confirm"},
    )
    pay_resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate", headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "combo-reward-pay"}
    )
    assert pay_resp.json()["status"] == "FAILED"  # the sale did NOT complete

    # The reward computed long before this failure is completely untouched.
    mine_resp = await client.get(
        "/api/v1/rewards/mine", headers={"Authorization": f"Bearer {await _login(client, 'combo-reward-home', 'homepass123')}"}
    )
    still_there = next(r for r in mine_resp.json()["rewards"] if r["reward_id"] == reward_id)
    assert still_there["amount"] == original_amount
    assert still_there["status"] == "CREDITED"


@pytest.mark.asyncio
async def test_the_same_idempotency_key_string_reused_across_different_endpoints_does_not_cross_contaminate(
    client, seeded_admin, accepted_bid_lot
):
    """Crosses the shared idempotency.py helper with two unrelated
    modules (bids and logistics): idempotency is scoped by
    (idempotency_key, scope), not by key alone — reusing the literal
    same key string for a completely different operation must not
    return the wrong cached response."""
    lot_id, _submission_id, bid_id, _amount = accepted_bid_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    shared_key = "reused-literal-key-across-modules"

    # First use: cancel the (already-ACCEPTED, so this must fail) bid —
    # doesn't matter that it fails, what matters is the key gets used in
    # the "bid_cancel" scope.
    cancel_resp = await client.post(
        f"/api/v1/bids/{bid_id}/cancel", headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": shared_key}
    )
    assert cancel_resp.status_code == 400  # ACCEPTED bids can't be cancelled this way

    # Second, unrelated use of the EXACT SAME key string, in the
    # "logistics_book" scope — must succeed normally, not return the
    # cached bid-cancel error or otherwise misbehave.
    book_resp = await client.post(
        f"/api/v1/logistics/{lot_id}/book", json={"slot_time": "2026-11-03T10:00:00Z"},
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": shared_key},
    )
    assert book_resp.status_code == 200, book_resp.text
    assert book_resp.json()["status"] == "BOOKED"


@pytest.mark.asyncio
async def test_a_complaint_filed_about_a_lot_never_alters_the_lots_own_state(
    client, seeded_admin, listed_lot, seeded_collector
):
    """Crosses the Phase 7 complaints module with the Phase 5/6 lot state
    machine: filing and reviewing a complaint that merely REFERENCES a
    lot must have zero effect on that lot's own status — complaints and
    marketplace state are deliberately unrelated systems."""
    lot_id, _submission_id = listed_lot
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    file_resp = await client.post(
        "/api/v1/complaints",
        json={"target_type": "lot", "target_id": lot_id, "category": "QUALITY", "description": "combined edge case"},
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    assert file_resp.status_code == 200
    complaint_id = file_resp.json()["complaint_id"]

    admin_token = await _login(client, "admin", "admin1234")
    await client.post(
        f"/api/v1/admin/complaints/{complaint_id}/review",
        json={"new_status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert lot_resp.json()["status"] == "LISTED_FOR_BIDDING"  # completely unchanged
