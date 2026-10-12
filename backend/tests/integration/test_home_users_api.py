import pytest


@pytest.mark.asyncio
async def test_home_user_can_register_and_login(client, seeded_ward):
    resp = await client.post(
        "/api/v1/home-users/register",
        json={
            "username": "citizen-1",
            "password": "citizenpass1",
            "full_name": "Citizen One",
            "address": "1 Main St",
            "ward_id": "WARD-1",
            "household_lat": 12.9716,
            "household_lng": 77.5946,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "citizen-1"

    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "citizen-1", "password": "citizenpass1"}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["role"] == "HOME_USER"


@pytest.mark.asyncio
async def test_registration_rejects_unknown_ward(client):
    resp = await client.post(
        "/api/v1/home-users/register",
        json={
            "username": "citizen-2",
            "password": "citizenpass1",
            "full_name": "Citizen Two",
            "address": "2 Main St",
            "ward_id": "NO-SUCH-WARD",
            "household_lat": 12.9716,
            "household_lng": 77.5946,
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "WARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_duplicate_username_rejected(client, seeded_ward):
    body = {
        "username": "citizen-3",
        "password": "citizenpass1",
        "full_name": "Citizen Three",
        "address": "3 Main St",
        "ward_id": "WARD-1",
        "household_lat": 12.9716,
        "household_lng": 77.5946,
    }
    resp1 = await client.post("/api/v1/home-users/register", json=body)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/home-users/register", json=body)
    assert resp2.status_code == 409
    assert resp2.json()["error_code"] == "USERNAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_home_user_me_returns_profile(client, seeded_home_user):
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "home-user-1", "password": "homepass123"}
    )
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/home-users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["ward_id"] == "WARD-1"


@pytest.mark.asyncio
async def test_non_home_user_rejected_on_me(client, seeded_recycler):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "RCY-001", "password": "recyclerpass1"})
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/home-users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_home_user_can_update_own_profile(client, seeded_home_user):
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "home-user-1", "password": "homepass123"}
    )
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        "/api/v1/home-users/me",
        json={"full_name": "Updated Name", "address": "Updated Address"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"
    assert resp.json()["address"] == "Updated Address"


@pytest.mark.asyncio
async def test_profile_update_rejects_empty_fields(client, seeded_home_user):
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "home-user-1", "password": "homepass123"}
    )
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        "/api/v1/home-users/me",
        json={"full_name": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_PROFILE"


@pytest.mark.asyncio
async def test_home_user_preferences_persist(client, seeded_home_user):
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "home-user-1", "password": "homepass123"}
    )
    token = login_resp.json()["access_token"]

    resp = await client.patch(
        "/api/v1/home-users/me/preferences",
        json={"language": "hin_Deva", "collection_updates": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["preferences"]["language"] == "hin_Deva"
    assert resp.json()["preferences"]["collection_updates"] is False

    refreshed = await client.get(
        "/api/v1/home-users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert refreshed.json()["preferences"]["language"] == "hin_Deva"


@pytest.mark.asyncio
async def test_deactivation_disables_account_and_invalidates_session(client, seeded_home_user):
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "home-user-1", "password": "homepass123"}
    )
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/home-users/me/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    blocked = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 403
    assert blocked.json()["error_code"] == "ACCOUNT_DISABLED"
