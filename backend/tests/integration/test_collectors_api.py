import pytest


@pytest.mark.asyncio
async def test_admin_can_create_collector(client, seeded_admin, seeded_ward):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/admin/collectors",
        json={"employee_id": "EMP-100", "password": "collectorpass1", "ward_id": "WARD-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == "EMP-100"
    assert resp.json()["ward_id"] == "WARD-1"


@pytest.mark.asyncio
async def test_collector_created_by_admin_can_login_with_employee_id(client, seeded_admin, seeded_ward):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]

    await client.post(
        "/api/v1/admin/collectors",
        json={"employee_id": "EMP-101", "password": "collectorpass1", "ward_id": "WARD-1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    collector_login = await client.post(
        "/api/v1/auth/login", json={"username": "EMP-101", "password": "collectorpass1"}
    )
    assert collector_login.status_code == 200
    assert collector_login.json()["role"] == "COLLECTOR"


@pytest.mark.asyncio
async def test_collector_self_registration_endpoint_does_not_exist(client):
    """No collector-facing self-registration endpoint should exist anywhere
    — only POST /api/v1/admin/collectors (admin-only) creates a collector."""
    resp = await client.post(
        "/api/v1/collectors/register",
        json={"employee_id": "EMP-999", "password": "whatever1"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_non_admin_cannot_create_collector(client, seeded_recycler, seeded_ward):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "RCY-001", "password": "recyclerpass1"})
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/admin/collectors",
        json={"employee_id": "EMP-102", "password": "collectorpass1", "ward_id": "WARD-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_two_different_collectors_can_be_created_in_a_row(client, seeded_admin, seeded_ward):
    """Regression guard: a real dev database was found carrying a stale
    plain-unique index on `phone` (a field this module has never written),
    left over from an unrelated legacy schema. That made every collector
    creation AFTER the first fail with a misleading INTERNAL_ERROR — the
    real DuplicateKeyError was on `phone: null`, not employee_id.
    mongomock starts clean and can't reproduce that exact bug, but it can
    at least catch a future regression where a bad plain-unique index on an
    unwritten field gets added to create_indexes() again."""
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp1 = await client.post(
        "/api/v1/admin/collectors",
        json={"employee_id": "EMP-200", "password": "collectorpass1", "ward_id": "WARD-1"},
        headers=headers,
    )
    assert resp1.status_code == 200, resp1.text

    resp2 = await client.post(
        "/api/v1/admin/collectors",
        json={"employee_id": "EMP-201", "password": "collectorpass1", "ward_id": "WARD-1"},
        headers=headers,
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["employee_id"] == "EMP-201"


@pytest.mark.asyncio
async def test_duplicate_employee_id_rejected(client, seeded_admin, seeded_ward):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    body = {"employee_id": "EMP-103", "password": "collectorpass1", "ward_id": "WARD-1"}

    resp1 = await client.post("/api/v1/admin/collectors", json=body, headers=headers)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/admin/collectors", json=body, headers=headers)
    assert resp2.status_code == 409
    assert resp2.json()["error_code"] == "USERNAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_collector_me_returns_profile(client, seeded_collector):
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "EMP-001", "password": "collectorpass1"}
    )
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/collectors/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["employee_id"] == "EMP-001"
    assert resp.json()["ward_id"] == "WARD-1"


@pytest.mark.asyncio
async def test_home_user_token_rejected_on_collector_endpoint(client, seeded_home_user):
    """RBAC isolation: a Home User's valid token must not work on a
    Collector-only endpoint, independent of any client-side navigation."""
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "home-user-1", "password": "homepass123"}
    )
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/collectors/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"
