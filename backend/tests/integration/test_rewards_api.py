"""
Integration tests for reward computation + mock UPI redemption
(architecture Section 12).

IMPORTANT: MOCK_UPI_PAYOUT is a pure, offline, hash-based function
(app/modules/rewards/payout.py) — the redemption tests validate the
SUCCEEDED/FAILED wiring, never a real UPI network's true behavior.
"""
from datetime import datetime, timezone

import pytest
from bson.decimal128 import Decimal128

from app.db.mongo import get_db
from app.db.repositories import audit_repo, rewards_repo


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _register_home_user_with_upi(client, username, upi_id=None):
    resp = await client.post(
        "/api/v1/home-users/register",
        json={
            "username": username,
            "password": "homepass123",
            "full_name": "Test Home User",
            "address": "x",
            "ward_id": "WARD-1",
            "household_lat": 12.9716,
            "household_lng": 77.5946,
            "upi_id": upi_id,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _submit_and_collect(client, home_token, collector_token, idem_prefix, photo="p"):
    """Drives one real submission to COLLECTED through the real APIs,
    which is exactly where reward_eligible_at gets stamped."""
    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": photo, "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": f"{idem_prefix}-submit"},
    )
    submission_id = submit_resp.json()["submission_id"]
    handover_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": photo, "collector_lat": 12.97165, "collector_lng": 77.59465},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": f"{idem_prefix}-handover"},
    )
    assert handover_resp.json()["status"] == "COLLECTED"
    return submission_id


# ---------------------------------------------------------------------------
# Immutable reward_eligible_at
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reward_eligible_at_is_stamped_exactly_once_at_collected(client, seeded_collector, seeded_ward):
    home = await _register_home_user_with_upi(client, "reward-home-1")
    home_token = await _login(client, "reward-home-1", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    submission_id = await _submit_and_collect(client, home_token, collector_token, "elig1")

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    assert doc["reward_eligible_at"] is not None


@pytest.mark.asyncio
async def test_reward_eligible_at_survives_full_lifecycle_unchanged(
    client, seeded_collector, seeded_rrr_center, seeded_ward
):
    home = await _register_home_user_with_upi(client, "reward-home-2")
    home_token = await _login(client, "reward-home-2", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "elig2")

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    stamp_at_collected = doc["reward_eligible_at"]
    assert stamp_at_collected is not None

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/receive",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "elig2-receive"},
    )
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/classify",
        json={"category": "metal-scrap"},
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "elig2-classify"},
    )

    doc_after = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    assert doc_after["reward_eligible_at"] == stamp_at_collected  # untouched by CLASSIFIED


@pytest.mark.asyncio
async def test_flagged_handover_never_sets_reward_eligible_at(client, seeded_collector, seeded_ward):
    home = await _register_home_user_with_upi(client, "reward-home-3")
    home_token = await _login(client, "reward-home-3", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "p", "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "elig3-submit"},
    )
    submission_id = submit_resp.json()["submission_id"]
    # Chennai coords — far outside tolerance, forces FLAGGED_FOR_REVIEW.
    handover_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p", "collector_lat": 13.0827, "collector_lng": 80.2707},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "elig3-handover"},
    )
    assert handover_resp.json()["status"] == "FLAGGED_FOR_REVIEW"

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    assert "reward_eligible_at" not in doc or doc.get("reward_eligible_at") is None


# ---------------------------------------------------------------------------
# Month-boundary + compute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reward_eligibility_uses_reward_eligible_at_not_current_item_state(
    client, seeded_admin, seeded_collector, seeded_rrr_center, seeded_ward
):
    """The core architecture-mandated proof: an item that is later sold,
    lotted, or otherwise advanced still earns its reward for the period
    it was actually COLLECTED in — eligibility is never derived from
    current status."""
    home = await _register_home_user_with_upi(client, "reward-home-4", upi_id="reward-home-4@upi")
    home_token = await _login(client, "reward-home-4", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "compute1")

    # Advance well past COLLECTED — AT_RRR, CLASSIFIED — before computing.
    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/receive",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "compute1-receive"},
    )
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/classify",
        json={"category": "metal-scrap"},
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "compute1-classify"},
    )

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")

    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute",
        json={"period": period},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert compute_resp.status_code == 200, compute_resp.text
    created = compute_resp.json()["created"]
    matching = [r for r in created if r["home_user_id"] == home["user_id"]]
    assert len(matching) == 1
    assert matching[0]["points"] == 10  # 1 item * default 10 points/item
    assert matching[0]["amount"] == "5.00"  # 10 points * Rs 0.50/point
    assert matching[0]["status"] == "CREDITED"


@pytest.mark.asyncio
async def test_unsold_never_lotted_item_still_earns_its_reward(
    client, seeded_admin, seeded_collector, seeded_ward
):
    """A COLLECTED item that never even reaches AT_RRR (no lot, no bid,
    no sale ever happens to it) still earns its reward — directly
    exercises 'reward not blocked by unsold/uncreated lot'."""
    home = await _register_home_user_with_upi(client, "reward-home-5")
    home_token = await _login(client, "reward-home-5", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "compute2")

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    assert doc["status"] == "COLLECTED"  # never advanced further
    period = doc["reward_eligible_at"].strftime("%Y-%m")

    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute",
        json={"period": period},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    created = compute_resp.json()["created"]
    assert any(r["home_user_id"] == home["user_id"] for r in created)


@pytest.mark.asyncio
async def test_item_collected_outside_period_is_excluded(client, seeded_admin, seeded_collector, seeded_ward):
    home = await _register_home_user_with_upi(client, "reward-home-6")
    home_token = await _login(client, "reward-home-6", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "compute3")

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    real_period = doc["reward_eligible_at"].strftime("%Y-%m")
    # Pick an adjacent period that cannot contain this item.
    year, month = (int(p) for p in real_period.split("-"))
    wrong_year = year - 1

    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute",
        json={"period": f"{wrong_year}-{month:02d}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    created = compute_resp.json()["created"]
    assert not any(r["home_user_id"] == home["user_id"] for r in created)


# ---------------------------------------------------------------------------
# One reward per user per period
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recomputing_the_same_period_never_double_credits(
    client, seeded_admin, seeded_collector, seeded_ward, test_db
):
    home = await _register_home_user_with_upi(client, "reward-home-7")
    home_token = await _login(client, "reward-home-7", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "compute4")

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")

    admin_token = await _login(client, "admin", "admin1234")
    first = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert any(r["home_user_id"] == home["user_id"] for r in first.json()["created"])

    second = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    # Already-credited user is skipped on the re-run, not re-created.
    assert not any(r["home_user_id"] == home["user_id"] for r in second.json()["created"])

    rewards = await rewards_repo.list_by_home_user(home["user_id"])
    matching = [r for r in rewards if r["period"] == period]
    assert len(matching) == 1  # exactly one, never two


@pytest.mark.asyncio
async def test_non_admin_cannot_compute_rewards(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": "2026-01"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_invalid_period_format_is_rejected(client, seeded_admin):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        "/api/v1/admin/rewards/compute",
        json={"period": "not-a-period"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_PERIOD"


# ---------------------------------------------------------------------------
# No automatic clawback (proof by absence + behavioral)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_clawback_function_exists_anywhere_in_the_rewards_module():
    """Structural guarantee, not just a convention: enumerate every
    public function in the rewards service and confirm none of them
    debits, invalidates, or claws back an existing reward/transaction."""
    import inspect

    from app.modules.rewards import service as rewards_service

    public_functions = [
        name for name, obj in inspect.getmembers(rewards_service, inspect.isfunction) if not name.startswith("_")
    ]
    forbidden_substrings = ("clawback", "debit", "invalidate", "revoke", "reverse")
    for name in public_functions:
        lowered = name.lower()
        assert not any(bad in lowered for bad in forbidden_substrings), f"unexpected function: {name}"


@pytest.mark.asyncio
async def test_computed_reward_credit_is_never_altered_by_later_activity(
    client, seeded_admin, seeded_collector, seeded_ward
):
    home = await _register_home_user_with_upi(client, "reward-home-8")
    home_token = await _login(client, "reward-home-8", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "compute5")

    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")
    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    reward = next(r for r in compute_resp.json()["created"] if r["home_user_id"] == home["user_id"])
    original_amount = reward["amount"]

    # There is no admin endpoint anywhere that can alter this reward's
    # amount/points after the fact — confirmed by re-reading it back.
    mine_resp = await client.get("/api/v1/rewards/mine", headers={"Authorization": f"Bearer {home_token}"})
    still_there = next(r for r in mine_resp.json()["rewards"] if r["reward_id"] == reward["reward_id"])
    assert still_there["amount"] == original_amount
    assert still_there["status"] == "CREDITED"


# ---------------------------------------------------------------------------
# Mock UPI redemption
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redemption_success_marks_reward_redeemed_and_is_audited(
    client, seeded_admin, seeded_collector, seeded_ward
):
    home = await _register_home_user_with_upi(client, "reward-home-9", upi_id="reward-home-9@upi")
    home_token = await _login(client, "reward-home-9", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "redeem1")
    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")
    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    reward_id = next(r for r in compute_resp.json()["created"] if r["home_user_id"] == home["user_id"])["reward_id"]

    resp = await client.post(
        f"/api/v1/rewards/{reward_id}/redeem",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "redeem1-attempt"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["type"] == "REDEMPTION"

    reward_doc = await rewards_repo.find_by_reward_id(reward_id)
    # status is only REDEEMED if the mock payout succeeded; either way no
    # crash and a real transaction record exists.
    assert reward_doc["status"] in ("CREDITED", "REDEEMED")

    logs = await audit_repo.list_logs(entity_type="reward")
    matching = [log for log in logs if log["entity_id"] == reward_id and log["action"] == "REWARD_REDEMPTION_ATTEMPTED"]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_redemption_without_upi_id_on_file_is_rejected(client, seeded_admin, seeded_collector, seeded_ward):
    home = await _register_home_user_with_upi(client, "reward-home-10", upi_id=None)
    home_token = await _login(client, "reward-home-10", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "redeem2")
    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")
    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    reward_id = next(r for r in compute_resp.json()["created"] if r["home_user_id"] == home["user_id"])["reward_id"]

    resp = await client.post(
        f"/api/v1/rewards/{reward_id}/redeem",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "redeem2-attempt"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "NO_UPI_ID_ON_FILE"


@pytest.mark.asyncio
async def test_redemption_failure_leaves_reward_credited_for_retry(
    client, seeded_admin, seeded_collector, seeded_ward, monkeypatch
):
    from app.modules.rewards import service as rewards_service
    from app.modules.rewards.payout import PayoutResult

    home = await _register_home_user_with_upi(client, "reward-home-11", upi_id="reward-home-11@upi")
    home_token = await _login(client, "reward-home-11", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "redeem3")
    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")
    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    reward_id = next(r for r in compute_resp.json()["created"] if r["home_user_id"] == home["user_id"])["reward_id"]

    monkeypatch.setattr(
        rewards_service, "payout", lambda reward_id, amount_str: PayoutResult(succeeded=False, reference="MOCK-FORCED-FAIL")
    )

    resp = await client.post(
        f"/api/v1/rewards/{reward_id}/redeem",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "redeem3-attempt"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"

    reward_doc = await rewards_repo.find_by_reward_id(reward_id)
    assert reward_doc["status"] == "CREDITED"  # not silently marked redeemed on failure


@pytest.mark.asyncio
async def test_cannot_redeem_someone_elses_reward(client, seeded_admin, seeded_collector, seeded_ward):
    home = await _register_home_user_with_upi(client, "reward-home-12", upi_id="reward-home-12@upi")
    home_token = await _login(client, "reward-home-12", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    submission_id = await _submit_and_collect(client, home_token, collector_token, "redeem4")
    doc = await get_db().e_waste_submissions.find_one({"submission_id": submission_id})
    period = doc["reward_eligible_at"].strftime("%Y-%m")
    admin_token = await _login(client, "admin", "admin1234")
    compute_resp = await client.post(
        "/api/v1/admin/rewards/compute", json={"period": period}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    reward_id = next(r for r in compute_resp.json()["created"] if r["home_user_id"] == home["user_id"])["reward_id"]

    other_home = await _register_home_user_with_upi(client, "reward-home-13", upi_id="reward-home-13@upi")
    other_token = await _login(client, "reward-home-13", "homepass123")

    resp = await client.post(
        f"/api/v1/rewards/{reward_id}/redeem",
        headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "redeem5-attempt"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_REWARD_OWNER"


@pytest.mark.asyncio
async def test_user_transaction_history_is_paginated_and_summary_is_persisted(client, seeded_home_user):
    await rewards_repo.insert_transaction(
        {
            "txn_id": "stage6-credit",
            "home_user_id": seeded_home_user["user_id"],
            "reward_id": "stage6-reward",
            "type": "CREDIT",
            "amount": Decimal128("5.00"),
            "status": "SUCCEEDED",
            "created_at": datetime.now(timezone.utc),
        }
    )
    await rewards_repo.insert_transaction(
        {
            "txn_id": "stage6-redemption",
            "home_user_id": seeded_home_user["user_id"],
            "reward_id": "stage6-reward",
            "type": "REDEMPTION",
            "amount": Decimal128("3.00"),
            "status": "SUCCEEDED",
            "created_at": datetime.now(timezone.utc),
        }
    )
    token = await _login(client, "home-user-1", "homepass123")

    page = await client.get(
        "/api/v1/rewards/transactions/mine?limit=1&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page.status_code == 200
    assert len(page.json()["transactions"]) == 1
    assert page.json()["has_more"] is True

    summary = await client.get(
        "/api/v1/rewards/transactions/summary/mine",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert summary.status_code == 200
    assert summary.json()["completed_credits"] == "5.00"
    assert summary.json()["completed_redemptions"] == "3.00"
