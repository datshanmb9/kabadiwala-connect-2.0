import pytest


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_recycler_can_register_and_login_while_pending(client):
    resp = await client.post(
        "/api/v1/recyclers/register",
        json={"username": "recycler-a", "password": "recyclerpass1", "company_name": "Recycler A Ltd"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PENDING"
    assert resp.json()["license_id"] == "recycler-a"

    login_resp = await client.post("/api/v1/auth/login", json={"username": "recycler-a", "password": "recyclerpass1"})
    assert login_resp.status_code == 200
    assert login_resp.json()["role"] == "RECYCLER"


@pytest.mark.asyncio
async def test_duplicate_license_id_rejected(client):
    body = {"username": "recycler-a", "password": "recyclerpass1", "company_name": "Recycler A Ltd"}
    resp1 = await client.post("/api/v1/recyclers/register", json=body)
    assert resp1.status_code == 200
    resp2 = await client.post("/api/v1/recyclers/register", json=body)
    assert resp2.status_code == 409
    assert resp2.json()["error_code"] in ("USERNAME_ALREADY_EXISTS", "LICENSE_ID_ALREADY_EXISTS")


@pytest.mark.asyncio
async def test_two_different_recyclers_can_register_in_a_row(client):
    """Regression guard: a real dev database was found carrying stale
    plain-unique indexes on `recycler_code`/`recycler_id` (fields this
    module has never written), left over from an unrelated legacy schema.
    A plain unique index treats every document missing the field as a
    colliding "null", so the first-ever legacy document already occupied
    that slot and EVERY subsequent registration failed at insert —
    misreported as LICENSE_ID_ALREADY_EXISTS even for a genuinely new
    license ID. mongomock starts clean and can't reproduce that exact bug,
    but it can at least catch a future regression where a bad plain-unique
    index on an unwritten field gets added to create_indexes() again."""
    resp1 = await client.post(
        "/api/v1/recyclers/register",
        json={"username": "recycler-first", "password": "recyclerpass1", "company_name": "First Co"},
    )
    assert resp1.status_code == 200, resp1.text

    resp2 = await client.post(
        "/api/v1/recyclers/register",
        json={"username": "recycler-second", "password": "recyclerpass1", "company_name": "Second Co"},
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["license_id"] == "recycler-second"


@pytest.mark.asyncio
async def test_pending_recycler_sees_own_status_via_me(client, pending_recycler):
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.get("/api/v1/recyclers/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"


@pytest.mark.asyncio
async def test_non_recycler_role_rejected_on_me(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.get("/api/v1/recyclers/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_admin_can_list_and_approve_recycler(client, seeded_admin, pending_recycler):
    admin_token = await _login(client, "admin", "admin1234")
    user, _profile = pending_recycler

    list_resp = await client.get("/api/v1/admin/recyclers", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp.status_code == 200
    assert any(r["license_id"] == "demo-recycler-1" for r in list_resp.json()["recyclers"])

    approve_resp = await client.post(
        f"/api/v1/admin/recyclers/{user['user_id']}/approve", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_admin_can_reject_a_pending_recycler(client, seeded_admin, pending_recycler):
    admin_token = await _login(client, "admin", "admin1234")
    user, _profile = pending_recycler

    resp = await client.post(
        f"/api/v1/admin/recyclers/{user['user_id']}/reject", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_cannot_approve_an_already_approved_recycler(client, seeded_admin, seeded_approved_recycler):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        f"/api/v1/admin/recyclers/{seeded_approved_recycler['user_id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "RECYCLER_NOT_PENDING"


@pytest.mark.asyncio
async def test_non_admin_cannot_approve_recycler(client, seeded_collector, pending_recycler):
    token = await _login(client, "EMP-001", "collectorpass1")
    user, _profile = pending_recycler
    resp = await client.post(
        f"/api/v1/admin/recyclers/{user['user_id']}/approve", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"
