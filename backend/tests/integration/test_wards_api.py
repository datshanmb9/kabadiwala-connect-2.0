import pytest


@pytest.mark.asyncio
async def test_admin_can_create_ward(client, seeded_admin):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/wards",
        json={"ward_id": "WARD-9", "name": "Ninth Ward"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["ward_id"] == "WARD-9"


@pytest.mark.asyncio
async def test_non_admin_cannot_create_ward(client, seeded_recycler):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "RCY-001", "password": "recyclerpass1"})
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/wards",
        json={"ward_id": "WARD-9", "name": "Ninth Ward"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_duplicate_ward_id_rejected(client, seeded_admin):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp1 = await client.post("/api/v1/wards", json={"ward_id": "WARD-9", "name": "Ninth Ward"}, headers=headers)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/wards", json={"ward_id": "WARD-9", "name": "Duplicate"}, headers=headers)
    assert resp2.status_code == 409
    assert resp2.json()["error_code"] == "WARD_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_authenticated_user_can_list_wards(client, seeded_admin, seeded_ward):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/wards", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    ward_ids = [w["ward_id"] for w in resp.json()["wards"]]
    assert "WARD-1" in ward_ids


@pytest.mark.asyncio
async def test_list_wards_is_public(client, seeded_ward):
    """Phase 3: made deliberately public so the Home User registration
    screen can show a ward picker before the user has an account/token.
    See the docstring on list_wards_route for the full rationale."""
    resp = await client.get("/api/v1/wards")
    assert resp.status_code == 200
    ward_ids = [w["ward_id"] for w in resp.json()["wards"]]
    assert "WARD-1" in ward_ids
