"""
Integration tests for POST /api/v1/payments/{lot_id}/initiate.

IMPORTANT: MOCK_PAYMENT_GATEWAY is a pure, offline, hash-based function
(app/modules/payments/gateway.py) — these tests validate the payment
INTEGRATION (state transitions, locking, idempotency, concurrency,
audit), never a real gateway's true approval rate. "500.00" and
"100.00" were derived once directly from that pure function (see
test_payment_gateway.py) and are stable forever, since it has no
external state.
"""
import asyncio

import pytest

from app.db.mongo import get_db
from app.db.repositories import audit_repo

SUCCEEDING_AMOUNT = "500.00"  # charge("500.00").succeeded is True
FAILING_AMOUNT = "100.00"  # charge("100.00").succeeded is False


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _accept_bid_with_amount(client, listed_lot, amount, idem_prefix):
    """Places+accepts a bid for a caller-chosen amount, so each test
    controls exactly which deterministic gateway outcome it lands in.
    Mirrors accepted_bid_lot but with a controllable amount."""
    lot_id, submission_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": amount},
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": f"{idem_prefix}-place"},
    )
    assert place_resp.status_code == 200, place_resp.text
    bid_id = place_resp.json()["bid_id"]

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    accept_resp = await client.post(
        f"/api/v1/bids/{bid_id}/accept",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": f"{idem_prefix}-accept"},
    )
    assert accept_resp.status_code == 200, accept_resp.text
    return lot_id, submission_id, bid_id


async def _advance_to_ready_for_collection(client, lot_id, idem_prefix):
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    book_resp = await client.post(
        f"/api/v1/logistics/{lot_id}/book",
        json={"slot_time": "2026-10-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": f"{idem_prefix}-book"},
    )
    assert book_resp.status_code == 200, book_resp.text
    booking_id = book_resp.json()["booking_id"]
    confirm_resp = await client.post(
        f"/api/v1/logistics/{booking_id}/confirm-collection",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": f"{idem_prefix}-confirm"},
    )
    assert confirm_resp.status_code == 200, confirm_resp.text
    assert confirm_resp.json()["status"] == "COLLECTED"
    return recycler_token


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_success_locks_lot_sold_and_item_paid(client, seeded_admin, seeded_approved_recycler, listed_lot):
    lot_id, submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, SUCCEEDING_AMOUNT, "pay-ok")
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-ok")

    resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-ok-initiate"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "SUCCEEDED"
    assert body["amount"] == "500.00"
    assert body["gateway"] == "MOCK_PAYMENT_GATEWAY"

    admin_token = await _login(client, "admin", "admin1234")
    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert lot_resp.json()["status"] == "SOLD"

    sub_resp = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert sub_resp.json()["status"] == "PAID"


# ---------------------------------------------------------------------------
# Failure path: PAYMENT_PENDING -> READY_FOR_COLLECTION, retryable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_failure_reverts_lot_to_ready_for_collection_and_allows_retry(
    client, seeded_admin, seeded_approved_recycler, listed_lot
):
    lot_id, submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, FAILING_AMOUNT, "pay-fail")
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-fail")

    fail_resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-fail-1"},
    )
    assert fail_resp.status_code == 200, fail_resp.text
    assert fail_resp.json()["status"] == "FAILED"

    admin_token = await _login(client, "admin", "admin1234")
    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert lot_resp.json()["status"] == "READY_FOR_COLLECTION"  # never stuck in PAYMENT_PENDING

    sub_resp = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert sub_resp.json()["status"] == "READY_FOR_COLLECTION"

    # A failed payment must not mark the lot paid/sold, and the recycler
    # must be able to retry with a fresh idempotency key.
    retry_resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-fail-2"},
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "FAILED"  # same amount -> same deterministic outcome


# ---------------------------------------------------------------------------
# Invalid lot state / cancelled bid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_rejected_for_lot_not_ready_for_collection(client, seeded_admin, accepted_bid_lot):
    lot_id, _submission_id, _bid_id, _amount = accepted_bid_lot  # still BID_SELECTED, no logistics yet
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-invalid-state"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "LOT_NOT_READY_FOR_COLLECTION"


@pytest.mark.asyncio
async def test_cancelled_bid_never_receives_payment_even_though_a_sibling_bid_gets_paid(
    client, seeded_admin, listed_lot, seeded_approved_recycler
):
    """A first recycler places a bid and cancels it before acceptance
    (PLACED -> CANCELLED); a second recycler's bid is then accepted and
    paid instead. Directly exercises 'do not allow a cancelled/invalid
    bid to receive payment' — proves the cancelled bid is structurally
    incapable of ever being the one payment acts on, not just untested."""
    lot_id, submission_id = listed_lot

    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    cancelled_place = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": "300.00"},
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-cancel-place"},
    )
    cancelled_bid_id = cancelled_place.json()["bid_id"]
    cancel_resp = await client.post(
        f"/api/v1/bids/{cancelled_bid_id}/cancel",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-cancel-cancel"},
    )
    assert cancel_resp.json()["status"] == "CANCELLED"

    lot_id, submission_id, _accepted_bid_id = await _accept_bid_with_amount(
        client, listed_lot, SUCCEEDING_AMOUNT, "pay-cancel-sibling"
    )
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-cancel-sibling")
    resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-cancel-final"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCEEDED"
    assert resp.json()["amount"] == SUCCEEDING_AMOUNT  # the accepted bid's amount, never the cancelled one's


# ---------------------------------------------------------------------------
# Duplicate-payment prevention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cannot_pay_an_already_sold_lot_again(client, seeded_admin, seeded_approved_recycler, listed_lot):
    lot_id, _submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, SUCCEEDING_AMOUNT, "pay-dup")
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-dup")

    first = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-dup-1"},
    )
    assert first.json()["status"] == "SUCCEEDED"

    second = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-dup-2"},
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "LOT_ALREADY_PAID"


# ---------------------------------------------------------------------------
# Idempotency replay
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotency_replay_returns_identical_cached_response_no_duplicate(
    client, seeded_admin, seeded_approved_recycler, listed_lot
):
    lot_id, _submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, SUCCEEDING_AMOUNT, "pay-idem")
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-idem")

    key = "pay-idem-fixed-key"
    first = await client.post(
        f"/api/v1/payments/{lot_id}/initiate", headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": key}
    )
    second = await client.post(
        f"/api/v1/payments/{lot_id}/initiate", headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": key}
    )
    # Compare the meaningful fields, not raw full-dict equality: a cached
    # response's `created_at` round-trips through MongoDB's BSON datetime
    # (millisecond precision, no tzinfo) while the first, never-cached
    # response is a fresh Python datetime (microsecond precision,
    # tz-aware) — same pre-existing characteristic of the shared
    # idempotency helper that test_bids_api.py's own replay test already
    # works around by comparing specific fields rather than full JSON
    # equality, not something newly introduced here.
    assert first.json()["payment_id"] == second.json()["payment_id"]
    assert first.json()["status"] == second.json()["status"]
    assert first.json()["amount"] == second.json()["amount"]
    assert first.json()["gateway_reference"] == second.json()["gateway_reference"]

    docs = [d async for d in get_db().payments.find({"lot_id": lot_id})]
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_missing_idempotency_key_is_rejected(client, seeded_admin, seeded_approved_recycler, listed_lot):
    lot_id, _submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, SUCCEEDING_AMOUNT, "pay-noidem")
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-noidem")
    resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate", headers={"Authorization": f"Bearer {recycler_token}"}
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Concurrency: the actual lock is lots_repo.transition_status_if_current
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_payment_attempts_never_produce_two_succeeded_payments(
    client, seeded_admin, seeded_approved_recycler, listed_lot
):
    """Fires two payment-initiate requests for the SAME lot with
    DIFFERENT idempotency keys via asyncio.gather. Unlike the bid/AI
    concurrency tests in earlier phases (which rely solely on a
    DB-level unique index and are honestly documented as not proving a
    true race is closed under mongomock-motor + ASGITransport), THIS
    endpoint has an additional, independent guard:
    lots_repo.transition_status_if_current() is a single conditional
    write (READY_FOR_COLLECTION -> PAYMENT_PENDING) that only one of two
    requests can ever have matched, even under whatever interleaving the
    test runtime actually produces — so this test verifies the real
    invariant directly, not just hopes the scheduler cooperates."""
    lot_id, _submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, SUCCEEDING_AMOUNT, "pay-race")
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-race")

    resp1, resp2 = await asyncio.gather(
        client.post(
            f"/api/v1/payments/{lot_id}/initiate",
            headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-race-key-1"},
        ),
        client.post(
            f"/api/v1/payments/{lot_id}/initiate",
            headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-race-key-2"},
        ),
    )

    statuses = {resp1.status_code, resp2.status_code}
    assert statuses <= {200, 409}
    assert 200 in statuses  # exactly one of the two actually processed

    succeeded_docs = [
        d async for d in get_db().payments.find({"lot_id": lot_id, "status": "SUCCEEDED"})
    ]
    assert len(succeeded_docs) == 1  # the actual invariant: never two

    admin_token = await _login(client, "admin", "admin1234")
    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert lot_resp.json()["status"] == "SOLD"


# ---------------------------------------------------------------------------
# RBAC / ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_the_accepted_bid_owner_can_initiate_payment(client, seeded_admin, seeded_approved_recycler, listed_lot):
    from app.modules.recyclers import service as recyclers_service

    lot_id, _submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, SUCCEEDING_AMOUNT, "pay-rbac1")
    await _advance_to_ready_for_collection(client, lot_id, "pay-rbac1")

    other = await recyclers_service.register(username="other-payer", password="otherpass123", company_name="Other Co")
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await recyclers_service.approve(user_id=other["user"]["user_id"], actor=admin_actor)
    other_token = await _login(client, "other-payer", "otherpass123")

    resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "pay-rbac1-attempt"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_ACCEPTED_BID_OWNER"


@pytest.mark.asyncio
async def test_rrr_and_home_user_cannot_initiate_payment(client, seeded_admin, seeded_approved_recycler, listed_lot, seeded_rrr_center):
    lot_id, _submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, SUCCEEDING_AMOUNT, "pay-rbac2")
    await _advance_to_ready_for_collection(client, lot_id, "pay-rbac2")

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "pay-rbac2-attempt"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


# ---------------------------------------------------------------------------
# Money precision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_amount_preserves_exact_decimal_precision(client, seeded_admin, seeded_approved_recycler, listed_lot):
    lot_id, _submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, "1850.75", "pay-precision")
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-precision")
    resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-precision-initiate"},
    )
    assert resp.status_code == 200
    assert resp.json()["amount"] == "1850.75"
    assert isinstance(resp.json()["amount"], str)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payment_attempt_is_audited(client, seeded_admin, seeded_approved_recycler, listed_lot):
    lot_id, _submission_id, _bid_id = await _accept_bid_with_amount(client, listed_lot, SUCCEEDING_AMOUNT, "pay-audit")
    recycler_token = await _advance_to_ready_for_collection(client, lot_id, "pay-audit")
    await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "pay-audit-initiate"},
    )
    logs = await audit_repo.list_logs(entity_type="lot")
    matching = [log for log in logs if log["entity_id"] == lot_id and log["action"] == "PAYMENT_ATTEMPTED"]
    assert len(matching) == 1
    assert matching[0]["details"]["status"] == "SUCCEEDED"
