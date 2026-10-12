import pytest

from app.db.repositories import audit_repo


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_recycler_can_book_logistics_for_own_accepted_bid(client, seeded_admin, accepted_bid_lot):
    lot_id, _submission_id, _bid_id, _amount = accepted_bid_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.post(
        f"/api/v1/logistics/{lot_id}/book",
        json={"slot_time": "2026-10-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "book-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "BOOKED"
    assert body["lot_id"] == lot_id


@pytest.mark.asyncio
async def test_booking_records_an_audit_event_and_moves_lot_and_item(
    client, seeded_admin, accepted_bid_lot, test_db
):
    lot_id, submission_id, _bid_id, _amount = accepted_bid_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    await client.post(
        f"/api/v1/logistics/{lot_id}/book",
        json={"slot_time": "2026-10-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "book-2"},
    )

    admin_token = await _login(client, "admin", "admin1234")
    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert lot_resp.json()["status"] == "LOGISTICS_BOOKED"

    sub_resp = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert sub_resp.json()["status"] == "LOGISTICS_BOOKED"

    logs = await audit_repo.list_logs(entity_type="lot")
    matching = [log for log in logs if log["entity_id"] == lot_id and log["action"] == "LOGISTICS_BOOKED"]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_cannot_book_logistics_twice_for_same_lot(client, seeded_admin, accepted_bid_lot):
    lot_id, _submission_id, _bid_id, _amount = accepted_bid_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    first = await client.post(
        f"/api/v1/logistics/{lot_id}/book",
        json={"slot_time": "2026-10-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "book-3a"},
    )
    assert first.status_code == 200
    second = await client.post(
        f"/api/v1/logistics/{lot_id}/book",
        json={"slot_time": "2026-10-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "book-3b"},
    )
    assert second.status_code == 400
    assert second.json()["error_code"] == "LOT_NOT_BID_SELECTED"


@pytest.mark.asyncio
async def test_only_the_accepted_bid_owner_can_book_logistics(client, seeded_admin, accepted_bid_lot):
    from app.modules.recyclers import service as recyclers_service

    lot_id, _submission_id, _bid_id, _amount = accepted_bid_lot
    other = await recyclers_service.register(username="other-recycler", password="otherpass123", company_name="Other Co")
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await recyclers_service.approve(user_id=other["user"]["user_id"], actor=admin_actor)
    other_token = await _login(client, "other-recycler", "otherpass123")

    resp = await client.post(
        f"/api/v1/logistics/{lot_id}/book",
        json={"slot_time": "2026-10-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "book-4"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_ACCEPTED_BID_OWNER"


@pytest.mark.asyncio
async def test_rrr_and_home_user_cannot_book_logistics(client, seeded_admin, accepted_bid_lot, seeded_rrr_center):
    lot_id, _submission_id, _bid_id, _amount = accepted_bid_lot
    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/logistics/{lot_id}/book",
        json={"slot_time": "2026-10-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "book-5"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_recycler_can_confirm_collection_and_it_is_idempotent(client, seeded_admin, logistics_booked_lot):
    lot_id, submission_id, _bid_id, _amount, booking_id = logistics_booked_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")

    resp = await client.post(
        f"/api/v1/logistics/{booking_id}/confirm-collection",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "confirm-1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COLLECTED"

    replay = await client.post(
        f"/api/v1/logistics/{booking_id}/confirm-collection",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "confirm-1"},
    )
    assert replay.json() == resp.json()

    admin_token = await _login(client, "admin", "admin1234")
    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert lot_resp.json()["status"] == "READY_FOR_COLLECTION"

    sub_resp = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert sub_resp.json()["status"] == "READY_FOR_COLLECTION"


@pytest.mark.asyncio
async def test_cannot_confirm_collection_before_booking(client, seeded_admin, accepted_bid_lot):
    lot_id, _submission_id, _bid_id, _amount = accepted_bid_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.post(
        "/api/v1/logistics/does-not-exist/confirm-collection",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "confirm-2"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "BOOKING_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_booking_for_lot_returns_the_real_booking(client, seeded_admin, logistics_booked_lot):
    lot_id, _submission_id, _bid_id, _amount, booking_id = logistics_booked_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.get(f"/api/v1/logistics/lot/{lot_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["booking"]["booking_id"] == booking_id


@pytest.mark.asyncio
async def test_get_booking_for_lot_returns_null_when_none_exists(client, seeded_admin, accepted_bid_lot):
    lot_id, _submission_id, _bid_id, _amount = accepted_bid_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.get(f"/api/v1/logistics/lot/{lot_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["booking"] is None


@pytest.mark.asyncio
async def test_cancelling_acceptance_after_logistics_booked_is_rejected(client, seeded_admin, logistics_booked_lot):
    """Real bug found and fixed during Phase 9: cancel_acceptance() used
    to hardcode the lot's 'from' state as BID_SELECTED regardless of the
    lot's actual current status, which would have silently reverted an
    already-LOGISTICS_BOOKED lot back to LISTED_FOR_BIDDING. This test
    proves the fix: once logistics has been booked, cancellation is
    rejected outright."""
    _lot_id, _submission_id, bid_id, _amount, _booking_id = logistics_booked_lot
    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/bids/{bid_id}/cancel-acceptance",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "cancel-after-logistics"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "LOT_NOT_BID_SELECTED"
