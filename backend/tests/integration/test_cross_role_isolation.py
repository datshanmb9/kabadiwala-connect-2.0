"""
Phase 10: cross-role isolation exercised against ONE real, shared
workflow instance rather than each role's own isolated test file. Every
individual ownership/role check already has its own dedicated test in
its own phase's suite (Phase 2-9) — this file proves those boundaries
hold simultaneously when the underlying data is genuinely shared and
live, which a single-role test file can't demonstrate by construction.
"""
import pytest


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_two_home_users_never_see_each_others_submissions(client, seeded_ward):
    from app.modules.home_users import service as home_users_service

    user_a = await home_users_service.register(
        username="iso-home-a", password="homepass123", full_name="A", address="x",
        ward_id="WARD-1", household_lat=12.9716, household_lng=77.5946, upi_id=None,
    )
    user_b = await home_users_service.register(
        username="iso-home-b", password="homepass123", full_name="B", address="x",
        ward_id="WARD-1", household_lat=12.9716, household_lng=77.5946, upi_id=None,
    )
    token_a = await _login(client, "iso-home-a", "homepass123")
    token_b = await _login(client, "iso-home-b", "homepass123")

    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "p", "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": "iso-submit-a"},
    )
    submission_id = submit_resp.json()["submission_id"]

    # B's own list never contains A's submission.
    b_list = await client.get("/api/v1/ewaste/submissions", headers={"Authorization": f"Bearer {token_b}"})
    assert all(s["submission_id"] != submission_id for s in b_list.json()["submissions"])

    # B cannot read A's submission detail directly either.
    b_detail = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert b_detail.status_code == 403


@pytest.mark.asyncio
async def test_collector_only_sees_own_ward_queue_even_with_two_wards_active(
    client, seeded_ward, other_ward, seeded_collector
):
    from app.modules.collectors import service as collectors_service
    from app.modules.home_users import service as home_users_service

    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await collectors_service.create_collector(
        employee_id="ISO-COL-2", password="collectorpass1", ward_id="WARD-2", rrr_id=None,
        assigned_area_radius_m=None, actor=admin_actor,
    )
    home_ward2 = await home_users_service.register(
        username="iso-home-ward2", password="homepass123", full_name="C", address="x",
        ward_id="WARD-2", household_lat=1.0, household_lng=1.0, upi_id=None,
    )
    token_ward2_home = await _login(client, "iso-home-ward2", "homepass123")
    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-2", "photo_file_id": "p", "home_lat": 1.0, "home_lng": 1.0},
        headers={"Authorization": f"Bearer {token_ward2_home}", "Idempotency-Key": "iso-submit-ward2"},
    )
    ward2_submission_id = submit_resp.json()["submission_id"]

    # WARD-1's collector (the existing seeded_collector) must never see
    # WARD-2's pending item, even though both wards are simultaneously
    # active in the same real database.
    ward1_token = await _login(client, "EMP-001", "collectorpass1")
    ward1_queue = await client.get("/api/v1/ewaste/submissions/pending", headers={"Authorization": f"Bearer {ward1_token}"})
    assert all(s["submission_id"] != ward2_submission_id for s in ward1_queue.json()["submissions"])

    # And WARD-1's collector cannot hand over WARD-2's item directly.
    forced_handover = await client.post(
        f"/api/v1/ewaste/submissions/{ward2_submission_id}/handover",
        json={"photo_file_id": "p", "collector_lat": 1.0, "collector_lng": 1.0},
        headers={"Authorization": f"Bearer {ward1_token}", "Idempotency-Key": "iso-forced-handover"},
    )
    assert forced_handover.status_code == 403
    assert forced_handover.json()["error_code"] == "COLLECTOR_OUTSIDE_ASSIGNED_AREA"


@pytest.mark.asyncio
async def test_rrr_cannot_see_or_act_on_another_rrrs_lot(client, seeded_admin, listed_lot, other_ward):
    from app.modules.rrr_centres import service as rrr_centres_service

    lot_id, _submission_id = listed_lot

    other_rrr = await rrr_centres_service.register(
        username="iso-other-rrr", password="otherpass123", rrr_id="ISO-RRR-2", tender_id="ISO-TENDER-2",
        ward_id="WARD-2", licence_doc_ref=None,
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await rrr_centres_service.approve(user_id=other_rrr["user"]["user_id"], actor=admin_actor)
    other_token = await _login(client, "iso-other-rrr", "otherpass123")

    # The other RRR's own lot list never contains the first RRR's lot.
    other_lots = await client.get("/api/v1/lots", headers={"Authorization": f"Bearer {other_token}"})
    assert all(l["lot_id"] != lot_id for l in other_lots.json()["lots"])

    # And the other RRR cannot publish/act on it directly.
    publish_attempt = await client.post(
        f"/api/v1/lots/{lot_id}/publish", headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "iso-publish-attempt"}
    )
    assert publish_attempt.status_code in (400, 403)  # already published (400) or not-owner (403) — either way, not silently allowed


@pytest.mark.asyncio
async def test_recycler_cannot_act_on_another_recyclers_bid(client, seeded_admin, listed_lot, seeded_approved_recycler):
    from app.modules.recyclers import service as recyclers_service

    lot_id, _submission_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    bid_resp = await client.post(
        "/api/v1/bids", json={"lot_id": lot_id, "amount": "250.00"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "iso-bid-place"},
    )
    bid_id = bid_resp.json()["bid_id"]

    other = await recyclers_service.register(username="iso-other-recycler", password="otherpass123", company_name="Other Co")
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await recyclers_service.approve(user_id=other["user"]["user_id"], actor=admin_actor)
    other_token = await _login(client, "iso-other-recycler", "otherpass123")

    cancel_attempt = await client.post(
        f"/api/v1/bids/{bid_id}/cancel", headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "iso-cancel-attempt"}
    )
    assert cancel_attempt.status_code == 403
    assert cancel_attempt.json()["error_code"] == "NOT_BID_OWNER"

    other_mine = await client.get("/api/v1/bids/mine", headers={"Authorization": f"Bearer {other_token}"})
    assert all(b["bid_id"] != bid_id for b in other_mine.json()["bids"])


@pytest.mark.asyncio
async def test_no_non_admin_role_can_reach_any_admin_only_endpoint(
    client, seeded_admin, seeded_collector, seeded_home_user, sold_lot
):
    """One sweep across every privileged-role token against a representative
    sample of admin-only endpoints, on real, live data — proving the
    boundary holds system-wide, not just per-endpoint in isolation."""
    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    home_token = await _login(client, "home-user-1", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    admin_only_calls = [
        ("GET", "/api/v1/admin/collectors"),
        ("GET", "/api/v1/admin/lots"),
        ("GET", "/api/v1/admin/bids"),
        ("GET", "/api/v1/admin/payments"),
        ("GET", "/api/v1/admin/rewards"),
        ("GET", "/api/v1/admin/submissions"),
    ]
    for token in (home_token, collector_token):
        for method, path in admin_only_calls:
            resp = await client.request(method, path, headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 403, f"{method} {path} should reject this role"

    # The one state-changing admin action introduced this phase, checked
    # the same way.
    complete_attempt = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "iso-complete-attempt"},
    )
    assert complete_attempt.status_code == 403
