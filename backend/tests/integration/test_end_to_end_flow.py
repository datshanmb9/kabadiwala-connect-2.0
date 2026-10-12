"""
Phase 10: ONE real chain through every module built since Phase 2,
proving the system behaves as one coherent whole rather than a
collection of individually-tested pieces. Every earlier phase's own
test suite already proves each individual link in isolation — this
file proves the links actually connect, using the real API surface
each frontend calls, never a shortcut through internal service
functions for the steps under test here.

Deliberately reuses HIGH_CONF/LOW_CONF photo ids and gateway amounts
already independently derived in Phase 8/9's own test suites (see
test_classification_api.py, test_payment_gateway.py) — same
determinism, not new magic numbers.
"""
import pytest

from app.db.mongo import get_db
from app.db.repositories import audit_repo
from app.modules.classification import service as classification_service
from tests.support.mock_classifier import DeterministicMockClassifier


@pytest.fixture(autouse=True)
def use_deterministic_classifier(monkeypatch):
    monkeypatch.setattr(
        classification_service,
        "get_classifier",
        lambda: DeterministicMockClassifier(),
    )


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_complete_lifecycle_home_user_to_redeemed_reward(client, seeded_admin, seeded_collector, seeded_rrr_center, seeded_approved_recycler):
    # --- Home User: register + submit ------------------------------------
    reg_resp = await client.post(
        "/api/v1/home-users/register",
        json={
            "username": "e2e-home-user", "password": "homepass123", "full_name": "E2E Home User",
            "address": "x", "ward_id": "WARD-1", "household_lat": 12.9716, "household_lng": 77.5946,
            "upi_id": "e2e-home-user@upi",
        },
    )
    assert reg_resp.status_code == 200, reg_resp.text
    home_user_id = reg_resp.json()["user_id"]
    home_token = await _login(client, "e2e-home-user", "homepass123")

    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "search-0", "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "e2e-submit"},
    )
    assert submit_resp.status_code == 200
    submission_id = submit_resp.json()["submission_id"]
    assert submit_resp.json()["status"] == "WAITING_FOR_COLLECTION"

    # --- Collector: geo-verified handover -> COLLECTED --------------------
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    handover_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "search-0", "collector_lat": 12.97165, "collector_lng": 77.59465},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "e2e-handover"},
    )
    assert handover_resp.status_code == 200
    assert handover_resp.json()["status"] == "COLLECTED"

    # reward_eligible_at is stamped here, immutably, and never touched
    # again by anything that follows in this test.
    doc_after_collect = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    reward_eligible_at = doc_after_collect["reward_eligible_at"]
    assert reward_eligible_at is not None
    period = reward_eligible_at.strftime("%Y-%m")

    # --- RRR: receive -> AT_RRR --------------------------------------------
    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    receive_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/receive",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "e2e-receive"},
    )
    assert receive_resp.json()["status"] == "AT_RRR"

    # --- AI classify: a deliberately LOW-confidence attempt first --------
    # "search-0" was the submission's own photo id (chosen for a
    # realistic geo pair above); classification uses a SEPARATE,
    # deliberately low-confidence id to exercise the NEEDS_REVIEW branch
    # — the classifier reads submission["photo_file_id"], which is
    # "search-0" (a high-confidence id per test_classification_api.py).
    # To genuinely exercise the low-confidence path in this end-to-end
    # chain, we drive a SECOND submission alongside the first rather than
    # mutating the first's photo reference (which nothing in this system
    # ever does after creation) — see the low-confidence sibling below.
    ai_resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "e2e-ai-1"},
    )
    assert ai_resp.status_code == 200, ai_resp.text
    assert ai_resp.json()["status"] == "CLASSIFIED"  # "search-0" is a known high-confidence id
    assert ai_resp.json()["source"] == "AI"
    category = ai_resp.json()["category"]
    assert category is not None

    # --- A sibling item to genuinely exercise NEEDS_REVIEW + manual resolve
    submit2_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "search-2", "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "e2e-submit-2"},
    )
    submission_id_2 = submit2_resp.json()["submission_id"]
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id_2}/handover",
        json={"photo_file_id": "search-2", "collector_lat": 12.97165, "collector_lng": 77.59465},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "e2e-handover-2"},
    )
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id_2}/receive",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "e2e-receive-2"},
    )
    ai_resp_2 = await client.post(
        f"/api/v1/ai/classify/{submission_id_2}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "e2e-ai-2"},
    )
    assert ai_resp_2.json()["status"] == "NEEDS_REVIEW"  # "search-2" is a known low-confidence id
    assert ai_resp_2.json()["category"] is None  # never silently accepted

    # Manual resolution, the same Phase 5 endpoint, now also valid from
    # NEEDS_REVIEW (Phase 8's widened eligibility check).
    manual_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id_2}/classify",
        json={"category": category},
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "e2e-manual-resolve"},
    )
    assert manual_resp.status_code == 200
    assert manual_resp.json()["status"] == "CLASSIFIED"

    # --- RRR: build + publish a lot containing BOTH items -----------------
    lot_resp = await client.post(
        "/api/v1/lots",
        json={"category": category, "submission_ids": [submission_id, submission_id_2]},
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "e2e-lot-create"},
    )
    assert lot_resp.status_code == 200, lot_resp.text
    lot_id = lot_resp.json()["lot_id"]
    publish_resp = await client.post(
        f"/api/v1/lots/{lot_id}/publish", headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "e2e-publish"}
    )
    assert publish_resp.json()["status"] == "LISTED_FOR_BIDDING"

    # --- Recycler: bid, RRR accepts -----------------------------------------
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    bid_resp = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": "500.00"},
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "e2e-bid-place"},
    )
    assert bid_resp.status_code == 200, bid_resp.text
    bid_id = bid_resp.json()["bid_id"]
    accept_resp = await client.post(
        f"/api/v1/bids/{bid_id}/accept", headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "e2e-bid-accept"}
    )
    assert accept_resp.json()["status"] == "ACCEPTED"

    # --- Recycler: logistics -----------------------------------------------
    book_resp = await client.post(
        f"/api/v1/logistics/{lot_id}/book",
        json={"slot_time": "2026-11-01T10:00:00Z"},
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "e2e-book"},
    )
    assert book_resp.status_code == 200, book_resp.text
    booking_id = book_resp.json()["booking_id"]
    confirm_resp = await client.post(
        f"/api/v1/logistics/{booking_id}/confirm-collection",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "e2e-confirm"},
    )
    assert confirm_resp.json()["status"] == "COLLECTED"

    # --- Recycler: payment (success, deterministic "500.00") ---------------
    pay_resp = await client.post(
        f"/api/v1/payments/{lot_id}/initiate",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "e2e-pay"},
    )
    assert pay_resp.status_code == 200, pay_resp.text
    assert pay_resp.json()["status"] == "SUCCEEDED"
    assert pay_resp.json()["amount"] == "500.00"

    admin_token = await _login(client, "admin", "admin1234")
    lot_after_pay = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert lot_after_pay.json()["status"] == "SOLD"
    for sid in (submission_id, submission_id_2):
        sub = await client.get(f"/api/v1/ewaste/submissions/{sid}", headers={"Authorization": f"Bearer {admin_token}"})
        assert sub.json()["status"] == "PAID"

    # --- Admin: complete the sale (Phase 10's new final step) --------------
    complete_resp = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "e2e-complete"},
    )
    assert complete_resp.status_code == 200, complete_resp.text
    assert complete_resp.json()["status"] == "COMPLETED"
    for sid in (submission_id, submission_id_2):
        sub = await client.get(f"/api/v1/ewaste/submissions/{sid}", headers={"Authorization": f"Bearer {admin_token}"})
        assert sub.json()["status"] == "COMPLETED"

    # --- Admin: compute rewards for the real period the item was COLLECTED
    # in — proving eligibility is keyed on reward_eligible_at, not on the
    # item's current (now COMPLETED, several steps later) status.
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert compute_resp.status_code == 200, compute_resp.text
    created = [r for r in compute_resp.json()["created"] if r["home_user_id"] == home_user_id]
    assert len(created) == 1
    reward = created[0]
    assert reward["points"] == 20  # 2 real items in this chain * 10 points/item
    assert reward["amount"] == "10.00"  # 20 points * Rs 0.50/point
    assert reward["status"] == "CREDITED"

    # --- Home User: mock UPI redemption -------------------------------------
    redeem_resp = await client.post(
        f"/api/v1/rewards/{reward['reward_id']}/redeem",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "e2e-redeem"},
    )
    assert redeem_resp.status_code == 200, redeem_resp.text
    assert redeem_resp.json()["type"] == "REDEMPTION"

    # --- Full audit trail present for every state-changing step ------------
    logs = await audit_repo.list_logs(limit=100)
    actions_seen = {log["action"] for log in logs}
    for expected_action in (
        "EWASTE_SUBMISSION_CREATED",
        "EWASTE_HANDOVER_RECORDED",
        "AI_CLASSIFICATION_ATTEMPTED",
        "EWASTE_CLASSIFIED",
        "LOT_CREATED",
        "LOT_PUBLISHED",
        "BID_PLACED",
        "BID_ACCEPTED",
        "LOGISTICS_BOOKED",
        "LOGISTICS_COLLECTION_CONFIRMED",
        "PAYMENT_ATTEMPTED",
        "LOT_COMPLETED",
        "REWARD_COMPUTED",
        "REWARD_REDEMPTION_ATTEMPTED",
    ):
        assert expected_action in actions_seen, f"missing audit action: {expected_action}"
