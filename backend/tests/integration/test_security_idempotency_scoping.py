"""
Phase 11 security fix verification: the idempotency cache was
previously keyed by (idempotency_key, scope) only — no user binding.
If two different accounts ever used the identical literal
idempotency-key string for the same scope, the second caller received
the FIRST caller's cached response, bypassing whatever ownership/
approval check ran on the original request (a cache hit short-circuits
before that check runs again). app/core/idempotency.py now scopes the
cache by (user_id, idempotency_key, scope).
"""
import pytest

from app.db.mongo import get_db


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_two_different_recyclers_reusing_the_same_literal_idempotency_key_get_independent_results(
    client, seeded_admin, seeded_approved_recycler, listed_lot
):
    from app.modules.recyclers import service as recyclers_service

    lot_id, _submission_id = listed_lot
    shared_key = "attacker-guessed-or-reused-key-value"

    token_a = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp_a = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": "111.00"},
        headers={"Authorization": f"Bearer {token_a}", "Idempotency-Key": shared_key},
    )
    assert resp_a.status_code == 200, resp_a.text
    bid_a = resp_a.json()

    other = await recyclers_service.register(username="idem-scope-recycler-b", password="otherpass123", company_name="B Co")
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await recyclers_service.approve(user_id=other["user"]["user_id"], actor=admin_actor)
    token_b = await _login(client, "idem-scope-recycler-b", "otherpass123")

    # Same literal key, same scope, DIFFERENT user, DIFFERENT amount —
    # must execute B's own request fresh, never return A's cached bid.
    resp_b = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": "222.00"},
        headers={"Authorization": f"Bearer {token_b}", "Idempotency-Key": shared_key},
    )
    assert resp_b.status_code == 200, resp_b.text
    bid_b = resp_b.json()

    assert bid_b["bid_id"] != bid_a["bid_id"]
    assert bid_b["recycler_id"] == "idem-scope-recycler-b"
    assert bid_b["amount"] == "222.00"
    # A's own response is untouched — never overwritten or leaked into.
    assert bid_a["recycler_id"] == "demo-recycler-1"
    assert bid_a["amount"] == "111.00"

    # Both records genuinely exist, independently, in the real collection.
    docs = [d async for d in get_db().bids.find({"lot_id": lot_id})]
    assert {d["bid_id"] for d in docs} == {bid_a["bid_id"], bid_b["bid_id"]}


@pytest.mark.asyncio
async def test_same_user_same_key_still_replays_correctly(client, seeded_admin, seeded_approved_recycler, listed_lot):
    """Regression guard: the user-scoping fix must not break the ordinary,
    intended case — the SAME user replaying their OWN key still gets
    their own cached response, no duplicate created."""
    lot_id, _submission_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    key = "same-user-replay-key"

    first = await client.post(
        "/api/v1/bids", json={"lot_id": lot_id, "amount": "333.00"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )
    second = await client.post(
        "/api/v1/bids", json={"lot_id": lot_id, "amount": "333.00"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key},
    )
    assert first.json()["bid_id"] == second.json()["bid_id"]

    docs = [d async for d in get_db().bids.find({"lot_id": lot_id, "recycler_id": "demo-recycler-1"})]
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_idempotency_documents_are_stored_with_a_user_id_field(client, seeded_admin, seeded_approved_recycler, listed_lot):
    """Direct structural proof against the real collection, not just
    behavioral — confirms the fix actually persists user_id, not just
    that behavior happens to look right."""
    lot_id, _submission_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    await client.post(
        "/api/v1/bids", json={"lot_id": lot_id, "amount": "444.00"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "structural-check-key"},
    )
    doc = await get_db().idempotency_keys.find_one({"idempotency_key": "structural-check-key"})
    assert doc is not None
    assert doc["user_id"]  # present and non-empty — not the pre-fix shape
