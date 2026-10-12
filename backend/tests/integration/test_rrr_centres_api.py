import pytest


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_rrr_centre_can_register_and_login_while_pending(client, seeded_ward):
    resp = await client.post(
        "/api/v1/rrr-centres/register",
        json={
            "username": "rrr-1",
            "password": "rrrpass123",
            "rrr_id": "RRR-001",
            "tender_id": "TENDER-001",
            "ward_id": "WARD-1",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PENDING"

    login_resp = await client.post("/api/v1/auth/login", json={"username": "rrr-1", "password": "rrrpass123"})
    assert login_resp.status_code == 200
    assert login_resp.json()["role"] == "RRR_CENTER"


@pytest.mark.asyncio
async def test_registration_rejects_unknown_ward(client):
    resp = await client.post(
        "/api/v1/rrr-centres/register",
        json={
            "username": "rrr-1",
            "password": "rrrpass123",
            "rrr_id": "RRR-001",
            "tender_id": "TENDER-001",
            "ward_id": "NO-SUCH-WARD",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "WARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_duplicate_rrr_id_rejected(client, seeded_ward, other_ward):
    body1 = {
        "username": "rrr-1", "password": "rrrpass123", "rrr_id": "RRR-001", "tender_id": "TENDER-001", "ward_id": "WARD-1",
    }
    body2 = {
        "username": "rrr-2", "password": "rrrpass123", "rrr_id": "RRR-001", "tender_id": "TENDER-002", "ward_id": "WARD-2",
    }
    resp1 = await client.post("/api/v1/rrr-centres/register", json=body1)
    assert resp1.status_code == 200
    resp2 = await client.post("/api/v1/rrr-centres/register", json=body2)
    assert resp2.status_code == 409
    assert resp2.json()["error_code"] == "RRR_ID_OR_TENDER_ID_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_pending_rrr_sees_own_status_via_me(client, pending_rrr_center):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.get("/api/v1/rrr-centres/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"


@pytest.mark.asyncio
async def test_non_rrr_role_rejected_on_me(client, seeded_recycler):
    token = await _login(client, "RCY-001", "recyclerpass1")
    resp = await client.get("/api/v1/rrr-centres/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_admin_can_list_and_approve_rrr_centre(client, seeded_admin, pending_rrr_center):
    admin_token = await _login(client, "admin", "admin1234")
    user, _profile = pending_rrr_center

    list_resp = await client.get(
        "/api/v1/admin/rrr-centres", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert list_resp.status_code == 200
    assert any(r["rrr_id"] == "RRR-001" for r in list_resp.json()["rrr_centres"])

    approve_resp = await client.post(
        f"/api/v1/admin/rrr-centres/{user['user_id']}/approve", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"

    wards_resp = await client.get("/api/v1/wards", headers={"Authorization": f"Bearer {admin_token}"})
    ward = next(w for w in wards_resp.json()["wards"] if w["ward_id"] == "WARD-1")
    assert ward["rrr_centre_id"] == "RRR-001"


@pytest.mark.asyncio
async def test_second_rrr_cannot_be_approved_for_the_same_ward(client, seeded_admin, seeded_ward):
    admin_token = await _login(client, "admin", "admin1234")

    async def register_and_approve(username, rrr_id, tender_id):
        resp = await client.post(
            "/api/v1/rrr-centres/register",
            json={
                "username": username, "password": "rrrpass123", "rrr_id": rrr_id, "tender_id": tender_id, "ward_id": "WARD-1",
            },
        )
        user_id = resp.json()["user_id"]
        return await client.post(
            f"/api/v1/admin/rrr-centres/{user_id}/approve", headers={"Authorization": f"Bearer {admin_token}"}
        )

    first = await register_and_approve("rrr-a", "RRR-A", "TENDER-A")
    assert first.status_code == 200

    second = await register_and_approve("rrr-b", "RRR-B", "TENDER-B")
    assert second.status_code == 409
    assert second.json()["error_code"] == "WARD_ALREADY_HAS_RRR_CENTRE"


@pytest.mark.asyncio
async def test_admin_can_reject_a_pending_rrr_centre(client, seeded_admin, pending_rrr_center):
    admin_token = await _login(client, "admin", "admin1234")
    user, _profile = pending_rrr_center

    resp = await client.post(
        f"/api/v1/admin/rrr-centres/{user['user_id']}/reject", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_cannot_approve_an_already_approved_rrr_centre(client, seeded_admin, seeded_rrr_center):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        f"/api/v1/admin/rrr-centres/{seeded_rrr_center['user_id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "RRR_NOT_PENDING"


@pytest.mark.asyncio
async def test_non_admin_cannot_approve_rrr_centre(client, seeded_recycler, pending_rrr_center):
    token = await _login(client, "RCY-001", "recyclerpass1")
    user, _profile = pending_rrr_center
    resp = await client.post(
        f"/api/v1/admin/rrr-centres/{user['user_id']}/approve", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"
