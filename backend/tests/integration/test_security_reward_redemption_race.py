"""
Phase 11 security fix verification: redeem_reward() previously did a
plain read-then-check with no atomic database guard, allowing two
concurrent redemption requests for the same reward to both pass the
CREDITED status check and both succeed against the mock payout — a
genuine duplicate-payout bug. rewards_repo.transition_status_if_current()
(mirroring lots_repo's Phase 9 payment-race guard) closes this.
"""
import asyncio

import pytest

from app.db.mongo import get_db
from app.db.repositories import rewards_repo


def _force_payout_success(monkeypatch):
    """app/modules/rewards/payout.py's mock is deterministic PER
    reward_id/amount but effectively random ACROSS reward_ids (~10% of
    hashes land on a simulated failure) — see test_rewards_api.py's own
    "either way no crash" comment for the same reason existing tests
    never hard-assert SUCCEEDED without controlling for this. These
    tests are about the concurrency guard, not payout randomness, so
    the outcome is pinned the same way test_failed_payout_reverts_...
    already does for the opposite case."""
    from app.modules.rewards import service as rewards_service
    from app.modules.rewards.payout import PayoutResult

    monkeypatch.setattr(
        rewards_service, "payout", lambda reward_id, amount_str: PayoutResult(succeeded=True, reference="MOCK-FORCED-SUCCESS")
    )


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _register_home_user_with_upi(client, username):
    resp = await client.post(
        "/api/v1/home-users/register",
        json={
            "username": username, "password": "homepass123", "full_name": "Race Test",
            "address": "x", "ward_id": "WARD-1", "household_lat": 12.9716, "household_lng": 77.5946,
            "upi_id": f"{username}@upi",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _credit_one_reward(client, seeded_collector, username):
    """Drives a real item to COLLECTED and computes a real reward for it —
    the exact same path test_rewards_api.py already uses."""
    home = await _register_home_user_with_upi(client, username)
    home_token = await _login(client, username, "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "p", "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": f"{username}-submit"},
    )
    submission_id = submit_resp.json()["submission_id"]
    handover_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p", "collector_lat": 12.97165, "collector_lng": 77.59465},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": f"{username}-handover"},
    )
    assert handover_resp.json()["status"] == "COLLECTED"

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")

    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    reward = next(r for r in compute_resp.json()["created"] if r["home_user_id"] == home["user_id"])
    return home_token, reward["reward_id"]


@pytest.mark.asyncio
async def test_concurrent_redemption_attempts_never_produce_two_succeeded_transactions(
    client, seeded_admin, seeded_collector, seeded_ward, monkeypatch
):
    """The actual proof: two genuinely concurrent redeem calls for the
    SAME reward, different idempotency keys. Same honest concurrency
    caveat already documented since Phase 6/9 — mongomock-motor +
    ASGITransport don't guarantee true interleaving — but the atomic
    conditional write means the safety invariant holds regardless of
    whatever interleaving the test runtime actually produces, exactly
    like the payment-race test this mirrors."""
    _force_payout_success(monkeypatch)
    home_token, reward_id = await _credit_one_reward(client, seeded_collector, "race-reward-home")

    resp1, resp2 = await asyncio.gather(
        client.post(
            f"/api/v1/rewards/{reward_id}/redeem",
            headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "race-redeem-key-1"},
        ),
        client.post(
            f"/api/v1/rewards/{reward_id}/redeem",
            headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "race-redeem-key-2"},
        ),
    )

    # The loser can legitimately land on either the pre-existing
    # "already CREDITED?" pre-check (400 REWARD_NOT_REDEEMABLE, if
    # mongomock/ASGITransport ran the two requests effectively
    # sequentially — the common case, same honest limitation documented
    # since the Phase 6 bid-acceptance and Phase 9 payment-race tests)
    # or the new atomic conditional-write guard itself (409, if the two
    # requests genuinely raced past the pre-check together). Either way
    # proves the real invariant below: never two SUCCEEDED redemptions.
    statuses = {resp1.status_code, resp2.status_code}
    assert statuses <= {200, 400, 409}
    assert 200 in statuses  # at least one genuinely processed

    # type="REDEMPTION" matters here — reward computation itself already
    # inserted a type="CREDIT" SUCCEEDED transaction for this same
    # reward_id before either redeem call ran; without this filter the
    # query below over-counts and looks like a duplicate payout when
    # there isn't one.
    succeeded_txns = [
        d
        async for d in get_db().reward_transactions.find(
            {"reward_id": reward_id, "type": "REDEMPTION", "status": "SUCCEEDED"}
        )
    ]
    assert len(succeeded_txns) == 1  # the actual invariant: never two

    reward_doc = await rewards_repo.find_by_reward_id(reward_id)
    assert reward_doc["status"] == "REDEEMED"  # never left stuck in the transient REDEEMING state


@pytest.mark.asyncio
async def test_second_redemption_attempt_after_success_is_a_clean_conflict(
    client, seeded_admin, seeded_collector, seeded_ward, monkeypatch
):
    _force_payout_success(monkeypatch)
    home_token, reward_id = await _credit_one_reward(client, seeded_collector, "sequential-reward-home")

    first = await client.post(
        f"/api/v1/rewards/{reward_id}/redeem",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "seq-redeem-1"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "SUCCEEDED"

    second = await client.post(
        f"/api/v1/rewards/{reward_id}/redeem",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "seq-redeem-2"},
    )
    assert second.status_code == 400
    assert second.json()["error_code"] == "REWARD_NOT_REDEEMABLE"


@pytest.mark.asyncio
async def test_failed_payout_reverts_reward_to_credited_for_retry(
    client, seeded_admin, seeded_collector, seeded_ward, monkeypatch
):
    from app.modules.rewards import service as rewards_service
    from app.modules.rewards.payout import PayoutResult

    home_token, reward_id = await _credit_one_reward(client, seeded_collector, "failed-payout-home")

    monkeypatch.setattr(
        rewards_service, "payout", lambda reward_id, amount_str: PayoutResult(succeeded=False, reference="MOCK-FORCED-FAIL")
    )
    resp = await client.post(
        f"/api/v1/rewards/{reward_id}/redeem",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "fail-redeem-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"

    reward_doc = await rewards_repo.find_by_reward_id(reward_id)
    assert reward_doc["status"] == "CREDITED"  # reverted, never stuck REDEEMING, retryable

    monkeypatch.undo()
    retry = await client.post(
        f"/api/v1/rewards/{reward_id}/redeem",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "fail-redeem-2"},
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "SUCCEEDED"
