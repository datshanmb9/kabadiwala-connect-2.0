"""
Integration tests for POST /api/v1/admin/lots/{lot_id}/complete — the
Phase 10 addition closing the previously-unreachable SOLD/PAID ->
COMPLETED gap found during Phase 10's integration audit. Does not
modify or re-test Phase 9's payment semantics; the `sold_lot` fixture
drives a real payment through the unchanged payments module first.
"""
import pytest

from app.db.mongo import get_db
from app.db.repositories import audit_repo


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_can_complete_a_sold_lot(client, seeded_admin, sold_lot):
    lot_id, submission_id, _bid_id, _amount, _booking_id = sold_lot
    admin_token = await _login(client, "admin", "admin1234")

    resp = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "complete-1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COMPLETED"

    lot_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert lot_resp.json()["status"] == "COMPLETED"

    sub_resp = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert sub_resp.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_completion_is_audited(client, seeded_admin, sold_lot):
    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    admin_token = await _login(client, "admin", "admin1234")
    await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "complete-audit"},
    )
    logs = await audit_repo.list_logs(entity_type="lot")
    matching = [log for log in logs if log["entity_id"] == lot_id and log["action"] == "LOT_COMPLETED"]
    assert len(matching) == 1
    assert matching[0]["actor_role"] == "GOVERNMENT_ADMIN"


@pytest.mark.asyncio
async def test_cannot_complete_a_lot_that_is_not_sold(client, seeded_admin, ready_for_collection_lot):
    lot_id, _submission_id, _bid_id, _amount, _booking_id = ready_for_collection_lot
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "complete-invalid"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "LOT_NOT_SOLD"


@pytest.mark.asyncio
async def test_cannot_complete_a_lot_that_was_never_paid_for(client, seeded_admin, listed_lot):
    lot_id, _submission_id = listed_lot
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "complete-never-paid"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "LOT_NOT_SOLD"


@pytest.mark.asyncio
async def test_completing_an_unknown_lot_is_not_found(client, seeded_admin):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        "/api/v1/admin/lots/does-not-exist/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "complete-404"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "LOT_NOT_FOUND"


# ---------------------------------------------------------------------------
# RBAC — admin/system-controlled only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recycler_cannot_complete_a_lot(client, seeded_admin, sold_lot):
    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "complete-rbac1"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_rrr_cannot_complete_a_lot(client, seeded_admin, sold_lot):
    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "complete-rbac2"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_home_user_and_collector_cannot_complete_a_lot(client, seeded_admin, sold_lot, seeded_home_user, seeded_collector):
    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    home_token = await _login(client, "home-user-1", "homepass123")
    resp1 = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "complete-rbac3"},
    )
    assert resp1.status_code == 403

    collector_token = await _login(client, "EMP-001", "collectorpass1")
    resp2 = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "complete-rbac4"},
    )
    assert resp2.status_code == 403


# ---------------------------------------------------------------------------
# Idempotency + repeated completion + backwards-transition prevention
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotency_replay_returns_identical_response_no_duplicate_transition(
    client, seeded_admin, sold_lot
):
    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    admin_token = await _login(client, "admin", "admin1234")
    key = "complete-idem-fixed"
    first = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete", headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": key}
    )
    second = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete", headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": key}
    )
    assert first.json() == second.json()

    logs = await audit_repo.list_logs(entity_type="lot")
    matching = [log for log in logs if log["entity_id"] == lot_id and log["action"] == "LOT_COMPLETED"]
    assert len(matching) == 1  # the cached replay never re-executed the transition/audit


@pytest.mark.asyncio
async def test_repeated_completion_with_a_new_key_is_rejected_not_reapplied(client, seeded_admin, sold_lot):
    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    admin_token = await _login(client, "admin", "admin1234")
    first = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "complete-repeat-1"},
    )
    assert first.json()["status"] == "COMPLETED"

    second = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "complete-repeat-2"},
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "LOT_ALREADY_COMPLETED"


@pytest.mark.asyncio
async def test_completed_lot_can_never_transition_backwards(client, seeded_admin, sold_lot):
    """Structural proof, not just the API-level rejection above: directly
    exercise the state machine's own allow-list for every backward edge
    a COMPLETED lot might be tempted to take."""
    from app.state_machines.lot_states import InvalidLotStateTransitionError, transition

    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    admin_token = await _login(client, "admin", "admin1234")
    await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "complete-backwards"},
    )

    for target in ("SOLD", "PAYMENT_PENDING", "READY_FOR_COLLECTION", "LOGISTICS_BOOKED", "BID_SELECTED", "LISTED_FOR_BIDDING", "DRAFT"):
        with pytest.raises(InvalidLotStateTransitionError):
            transition("COMPLETED", target)


@pytest.mark.asyncio
async def test_missing_idempotency_key_is_rejected(client, seeded_admin, sold_lot):
    lot_id, _submission_id, _bid_id, _amount, _booking_id = sold_lot
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        f"/api/v1/admin/lots/{lot_id}/complete", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 422
