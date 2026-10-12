import asyncio
from datetime import datetime, timedelta, timezone

import pytest


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _place_bid(client, token, lot_id, amount, idem_key):
    return await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": amount},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idem_key},
    )


# --- Placing a bid --------------------------------------------------------


@pytest.mark.asyncio
async def test_approved_recycler_can_place_a_bid(client, seeded_approved_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await _place_bid(client, token, lot_id, "1250.50", "place-bid-1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "PLACED"
    assert body["amount"] == "1250.50"
    assert body["lot_id"] == lot_id
    assert body["recycler_id"] == "demo-recycler-1"


@pytest.mark.asyncio
async def test_pending_recycler_cannot_place_a_bid(client, pending_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await _place_bid(client, token, lot_id, "100", "place-bid-pending")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "RECYCLER_NOT_APPROVED"


@pytest.mark.asyncio
async def test_non_recycler_role_cannot_place_a_bid(client, seeded_rrr_center, listed_lot):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await _place_bid(client, token, lot_id, "100", "place-bid-wrong-role")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_bid_requires_idempotency_key_header(client, seeded_approved_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.post(
        "/api/v1/bids", json={"lot_id": lot_id, "amount": "100"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bid_on_nonexistent_lot_rejected(client, seeded_approved_recycler):
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await _place_bid(client, token, "no-such-lot", "100", "place-bid-no-lot")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "LOT_NOT_FOUND"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_amount", ["not-a-number", "0", "-50", "12.999", ""])
async def test_invalid_bid_amounts_rejected(client, seeded_approved_recycler, listed_lot, bad_amount):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await _place_bid(client, token, lot_id, bad_amount, f"place-bid-bad-{bad_amount}")
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "INVALID_BID_AMOUNT"


@pytest.mark.asyncio
async def test_bid_after_deadline_rejected(client, seeded_approved_recycler, listed_lot):
    from app.db.repositories import lots_repo

    lot_id, _sub_id = listed_lot
    # Push the real lot's deadline into the past, directly at the data
    # layer — proving the server enforces this itself, not just trusting
    # whatever deadline the client last saw client-side.
    past_deadline = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    await lots_repo.update_status_and_deadline(lot_id, "LISTED_FOR_BIDDING", past_deadline)

    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await _place_bid(client, token, lot_id, "100", "place-bid-past-deadline")
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "BID_DEADLINE_PASSED"


@pytest.mark.asyncio
async def test_bid_on_non_listed_lot_rejected(client, seeded_approved_recycler, listed_lot):
    from app.db.repositories import lots_repo

    lot_id, _sub_id = listed_lot
    await lots_repo.update_status(lot_id, "DRAFT")

    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await _place_bid(client, token, lot_id, "100", "place-bid-not-listed")
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "LOT_NOT_LISTED_FOR_BIDDING"


@pytest.mark.asyncio
async def test_bid_idempotency_replay_returns_same_bid_no_duplicate(client, seeded_approved_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")

    resp1 = await _place_bid(client, token, lot_id, "500", "replay-bid-key")
    resp2 = await _place_bid(client, token, lot_id, "500", "replay-bid-key")

    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json()["bid_id"] == resp2.json()["bid_id"]

    mine_resp = await client.get("/api/v1/bids/mine", headers={"Authorization": f"Bearer {token}"})
    assert len(mine_resp.json()["bids"]) == 1


# --- Cancelling a bid ------------------------------------------------------


@pytest.mark.asyncio
async def test_recycler_can_cancel_own_placed_bid(client, seeded_approved_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, token, lot_id, "100", "cancel-bid-place")
    bid_id = place_resp.json()["bid_id"]

    cancel_resp = await client.post(
        f"/api/v1/bids/{bid_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cancel-bid-key"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cannot_cancel_another_recyclers_bid(client, seeded_approved_recycler, listed_lot):
    from app.modules.recyclers import service as recyclers_service

    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, token, lot_id, "100", "cancel-bid-other-place")
    bid_id = place_resp.json()["bid_id"]

    other_result = await recyclers_service.register(
        username="other-recycler", password="recyclerpass123", company_name="Other Co"
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await recyclers_service.approve(user_id=other_result["user"]["user_id"], actor=admin_actor)
    other_token = await _login(client, "other-recycler", "recyclerpass123")

    resp = await client.post(
        f"/api/v1/bids/{bid_id}/cancel",
        headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "cancel-bid-other-key"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_BID_OWNER"


@pytest.mark.asyncio
async def test_cannot_cancel_an_already_cancelled_bid(client, seeded_approved_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, token, lot_id, "100", "cancel-twice-place")
    bid_id = place_resp.json()["bid_id"]

    await client.post(
        f"/api/v1/bids/{bid_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cancel-twice-1"},
    )
    resp2 = await client.post(
        f"/api/v1/bids/{bid_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cancel-twice-2"},
    )
    assert resp2.status_code == 400
    assert resp2.json()["error_code"] == "BID_NOT_CANCELLABLE"


# --- Accepting a bid (RRR, own lot) ----------------------------------------


@pytest.mark.asyncio
async def test_rrr_can_accept_a_bid_on_own_lot(client, seeded_admin, seeded_approved_recycler, listed_lot):
    lot_id, sub_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, recycler_token, lot_id, "999.99", "accept-bid-place")
    bid_id = place_resp.json()["bid_id"]

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    accept_resp = await client.post(
        f"/api/v1/bids/{bid_id}/accept",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "accept-bid-key"},
    )
    assert accept_resp.status_code == 200, accept_resp.text
    assert accept_resp.json()["status"] == "ACCEPTED"
    assert accept_resp.json()["accepted_at"] is not None

    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {rrr_token}"})
    assert lot_resp.json()["status"] == "BID_SELECTED"

    admin_token = await _login(client, "admin", "admin1234")
    submission_resp = await client.get(
        f"/api/v1/ewaste/submissions/{sub_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert submission_resp.json()["status"] == "BID_SELECTED"


@pytest.mark.asyncio
async def test_accepting_a_bid_rejects_sibling_bids(client, seeded_approved_recycler, listed_lot):
    from app.modules.recyclers import service as recyclers_service

    lot_id, _sub_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    winning_resp = await _place_bid(client, recycler_token, lot_id, "800", "sibling-winning-bid")
    winning_bid_id = winning_resp.json()["bid_id"]

    other_result = await recyclers_service.register(
        username="losing-recycler", password="recyclerpass123", company_name="Losing Co"
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await recyclers_service.approve(user_id=other_result["user"]["user_id"], actor=admin_actor)
    losing_token = await _login(client, "losing-recycler", "recyclerpass123")
    losing_resp = await _place_bid(client, losing_token, lot_id, "700", "sibling-losing-bid")
    losing_bid_id = losing_resp.json()["bid_id"]

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    accept_resp = await client.post(
        f"/api/v1/bids/{winning_bid_id}/accept",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "sibling-accept-key"},
    )
    assert accept_resp.status_code == 200

    mine_resp = await client.get("/api/v1/bids/mine", headers={"Authorization": f"Bearer {losing_token}"})
    losing_bid = next(b for b in mine_resp.json()["bids"] if b["bid_id"] == losing_bid_id)
    assert losing_bid["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_non_owner_rrr_cannot_accept_bid(client, seeded_approved_recycler, listed_lot, other_ward):
    from app.modules.rrr_centres import service as rrr_centres_service

    lot_id, _sub_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, recycler_token, lot_id, "100", "non-owner-accept-place")
    bid_id = place_resp.json()["bid_id"]

    other_rrr_result = await rrr_centres_service.register(
        username="other-rrr", password="rrrpass123", rrr_id="RRR-OTHER", tender_id="TENDER-OTHER", ward_id="WARD-2",
        licence_doc_ref=None,
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await rrr_centres_service.approve(user_id=other_rrr_result["user"]["user_id"], actor=admin_actor)
    other_token = await _login(client, "other-rrr", "rrrpass123")

    resp = await client.post(
        f"/api/v1/bids/{bid_id}/accept",
        headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "non-owner-accept-key"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_LOT_OWNER"


@pytest.mark.asyncio
async def test_recycler_cannot_accept_a_bid(client, seeded_approved_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, token, lot_id, "100", "recycler-accept-place")
    bid_id = place_resp.json()["bid_id"]

    resp = await client.post(
        f"/api/v1/bids/{bid_id}/accept",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "recycler-accept-key"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


# --- Concurrency: exactly one accept can ever win ---------------------------


@pytest.mark.asyncio
async def test_two_different_recyclers_cannot_both_be_accepted_for_same_lot(client, seeded_approved_recycler, listed_lot):
    """The architecture's own named concurrency test (Section 15): fire two
    'accept' requests for two different bids on the same lot at once. The
    safety property under test is the outcome invariant: it must never be
    possible for both to end up ACCEPTED. Note on what this test can and
    can't prove here: httpx.ASGITransport + mongomock-motor run both
    coroutines in the same process against an in-memory store, and do not
    reliably interleave two requests the way two real client connections
    against a real `mongod` would — in practice the second request here
    typically doesn't overlap the first's write at all, so it's usually
    caught by the service layer's own PLACED-status pre-check
    (BID_NOT_ACCEPTABLE, once sibling-rejection has already run) rather
    than by the database racing on the partial unique index
    (LOT_ALREADY_ACCEPTED) — both are legitimate rejections of the loser,
    just via different code paths depending on how the scheduler
    interleaves them. The DB-level partial unique index on
    bids.(lot_id, status=ACCEPTED) is real and additive defense-in-depth,
    same as documented for other partial-unique-index cases since Phase 2
    (mongomock's index enforcement is not a perfect stand-in for real
    MongoDB's concurrency behavior) — this test proves the invariant
    holds, not which specific code path enforced it on a given run."""
    from app.modules.recyclers import service as recyclers_service

    lot_id, _sub_id = listed_lot
    recycler_a_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    bid_a_resp = await _place_bid(client, recycler_a_token, lot_id, "500", "concurrency-bid-a")
    bid_a_id = bid_a_resp.json()["bid_id"]

    recycler_b_result = await recyclers_service.register(
        username="concurrency-recycler-b", password="recyclerpass123", company_name="B Co"
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await recyclers_service.approve(user_id=recycler_b_result["user"]["user_id"], actor=admin_actor)
    recycler_b_token = await _login(client, "concurrency-recycler-b", "recyclerpass123")
    bid_b_resp = await _place_bid(client, recycler_b_token, lot_id, "600", "concurrency-bid-b")
    bid_b_id = bid_b_resp.json()["bid_id"]

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")

    accept_a, accept_b = await asyncio.gather(
        client.post(
            f"/api/v1/bids/{bid_a_id}/accept",
            headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "concurrency-accept-a"},
        ),
        client.post(
            f"/api/v1/bids/{bid_b_id}/accept",
            headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "concurrency-accept-b"},
        ),
    )

    statuses = sorted([accept_a.status_code, accept_b.status_code])
    assert statuses == [200, 400] or statuses == [200, 409], (accept_a.text, accept_b.text)
    loser = accept_a if accept_a.status_code != 200 else accept_b
    assert loser.json()["error_code"] in ("LOT_ALREADY_ACCEPTED", "BID_NOT_ACCEPTABLE")

    # The actual safety property: exactly one bid on this lot is ever
    # ACCEPTED, never both, regardless of which HTTP path the loser hit.
    mine_a = await client.get("/api/v1/bids/mine", headers={"Authorization": f"Bearer {recycler_a_token}"})
    mine_b = await client.get("/api/v1/bids/mine", headers={"Authorization": f"Bearer {recycler_b_token}"})
    all_statuses = [b["status"] for b in mine_a.json()["bids"]] + [b["status"] for b in mine_b.json()["bids"]]
    assert all_statuses.count("ACCEPTED") == 1


# --- Cancelling an acceptance (RRR, own lot, within window) -----------------


@pytest.mark.asyncio
async def test_rrr_can_cancel_acceptance_within_window(client, seeded_admin, seeded_approved_recycler, listed_lot):
    lot_id, sub_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, recycler_token, lot_id, "100", "cancel-accept-place")
    bid_id = place_resp.json()["bid_id"]

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    await client.post(
        f"/api/v1/bids/{bid_id}/accept",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "cancel-accept-accept-key"},
    )

    cancel_resp = await client.post(
        f"/api/v1/bids/{bid_id}/cancel-acceptance",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "cancel-accept-key"},
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "CANCELLED"

    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {rrr_token}"})
    assert lot_resp.json()["status"] == "LISTED_FOR_BIDDING"

    admin_token = await _login(client, "admin", "admin1234")
    submission_resp = await client.get(
        f"/api/v1/ewaste/submissions/{sub_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert submission_resp.json()["status"] == "LISTED_FOR_BIDDING"


@pytest.mark.asyncio
async def test_cannot_cancel_acceptance_after_window_expires(client, seeded_approved_recycler, listed_lot):
    from app.db.repositories import bids_repo

    lot_id, _sub_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, recycler_token, lot_id, "100", "expired-accept-place")
    bid_id = place_resp.json()["bid_id"]

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    await client.post(
        f"/api/v1/bids/{bid_id}/accept",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "expired-accept-accept-key"},
    )

    # Directly backdate accepted_at at the data layer to simulate 25h
    # having passed, rather than sleeping in a test — this still proves
    # the server enforces its own clock, not a client-supplied one.
    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25)
    await bids_repo.update_status(bid_id, "ACCEPTED", accepted_at=stale_time)

    resp = await client.post(
        f"/api/v1/bids/{bid_id}/cancel-acceptance",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "expired-accept-cancel-key"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "ACCEPTANCE_CANCEL_WINDOW_EXPIRED"


@pytest.mark.asyncio
async def test_cannot_cancel_acceptance_on_a_bid_that_was_never_accepted(client, seeded_approved_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await _place_bid(client, recycler_token, lot_id, "100", "never-accepted-place")
    bid_id = place_resp.json()["bid_id"]

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/bids/{bid_id}/cancel-acceptance",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "never-accepted-cancel-key"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "BID_NOT_CANCELLABLE"


# --- RRR viewing bids on its own lot ----------------------------------------


@pytest.mark.asyncio
async def test_rrr_can_list_bids_on_own_lot(client, seeded_approved_recycler, listed_lot):
    lot_id, _sub_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    await _place_bid(client, recycler_token, lot_id, "321", "list-bids-place")

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.get(f"/api/v1/lots/{lot_id}/bids", headers={"Authorization": f"Bearer {rrr_token}"})
    assert resp.status_code == 200
    amounts = [b["amount"] for b in resp.json()["bids"]]
    assert "321" in amounts


@pytest.mark.asyncio
async def test_non_owner_rrr_cannot_list_bids_on_a_lot(client, seeded_approved_recycler, listed_lot, other_ward):
    from app.modules.rrr_centres import service as rrr_centres_service

    lot_id, _sub_id = listed_lot
    other_rrr_result = await rrr_centres_service.register(
        username="bids-list-other-rrr", password="rrrpass123", rrr_id="RRR-BL", tender_id="TENDER-BL",
        ward_id="WARD-2", licence_doc_ref=None,
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await rrr_centres_service.approve(user_id=other_rrr_result["user"]["user_id"], actor=admin_actor)
    other_token = await _login(client, "bids-list-other-rrr", "rrrpass123")

    resp = await client.get(f"/api/v1/lots/{lot_id}/bids", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_LOT_OWNER"
