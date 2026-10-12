import pytest

from app.db.repositories import audit_repo


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_any_authenticated_role_can_file_a_complaint(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.post(
        "/api/v1/complaints",
        json={
            "target_type": "ward",
            "target_id": "WARD-1",
            "category": "SAFETY",
            "description": "Unsafe handling observed.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "OPEN"
    assert body["reporter_role"] == "COLLECTOR"
    assert body["reporter_id"]  # never client-supplied, always the token's own user_id


@pytest.mark.asyncio
async def test_filing_requires_authentication(client):
    resp = await client.post(
        "/api/v1/complaints",
        json={"target_type": "ward", "target_id": "WARD-1", "category": "X", "description": "y"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_filing_records_an_audit_event(client, seeded_collector, test_db):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.post(
        "/api/v1/complaints",
        json={"target_type": "ward", "target_id": "WARD-1", "category": "SAFETY", "description": "d"},
        headers={"Authorization": f"Bearer {token}"},
    )
    complaint_id = resp.json()["complaint_id"]

    logs = await audit_repo.list_logs(actor_role="COLLECTOR", entity_type="complaint")
    matching = [log for log in logs if log["entity_id"] == complaint_id]
    assert len(matching) == 1
    assert matching[0]["action"] == "COMPLAINT_FILED"
    assert matching[0]["details"]["category"] == "SAFETY"


@pytest.mark.asyncio
async def test_reporter_sees_own_complaint_in_mine(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    await client.post(
        "/api/v1/complaints",
        json={"target_type": "ward", "target_id": "WARD-1", "category": "X", "description": "y"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/api/v1/complaints/mine", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["complaints"]) == 1


@pytest.mark.asyncio
async def test_non_admin_cannot_list_all_complaints(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.get("/api/v1/admin/complaints", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_admin_can_list_all_complaints(client, seeded_admin, seeded_collector):
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    await client.post(
        "/api/v1/complaints",
        json={"target_type": "ward", "target_id": "WARD-1", "category": "X", "description": "y"},
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get("/api/v1/admin/complaints", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()["complaints"]) == 1


@pytest.mark.asyncio
async def test_admin_can_review_open_to_in_progress_and_it_is_audited(client, seeded_admin, seeded_collector, test_db):
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    file_resp = await client.post(
        "/api/v1/complaints",
        json={"target_type": "ward", "target_id": "WARD-1", "category": "X", "description": "y"},
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    complaint_id = file_resp.json()["complaint_id"]

    admin_token = await _login(client, "admin", "admin1234")
    review_resp = await client.post(
        f"/api/v1/admin/complaints/{complaint_id}/review",
        json={"new_status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "IN_PROGRESS"

    logs = await audit_repo.list_logs(actor_role="GOVERNMENT_ADMIN", entity_type="complaint")
    matching = [log for log in logs if log["entity_id"] == complaint_id and log["action"] == "COMPLAINT_REVIEWED"]
    assert len(matching) == 1
    assert matching[0]["details"] == {"from_status": "OPEN", "to_status": "IN_PROGRESS"}


@pytest.mark.asyncio
async def test_admin_can_resolve_with_notes_after_in_progress(client, seeded_admin, seeded_collector):
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    file_resp = await client.post(
        "/api/v1/complaints",
        json={"target_type": "ward", "target_id": "WARD-1", "category": "X", "description": "y"},
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    complaint_id = file_resp.json()["complaint_id"]

    admin_token = await _login(client, "admin", "admin1234")
    await client.post(
        f"/api/v1/admin/complaints/{complaint_id}/review",
        json={"new_status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resolve_resp = await client.post(
        f"/api/v1/admin/complaints/{complaint_id}/review",
        json={"new_status": "RESOLVED", "resolution_notes": "Fixed on site."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "RESOLVED"
    assert resolve_resp.json()["resolution_notes"] == "Fixed on site."


@pytest.mark.asyncio
async def test_cannot_skip_straight_from_open_to_resolved(client, seeded_admin, seeded_collector):
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    file_resp = await client.post(
        "/api/v1/complaints",
        json={"target_type": "ward", "target_id": "WARD-1", "category": "X", "description": "y"},
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    complaint_id = file_resp.json()["complaint_id"]

    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        f"/api/v1/admin/complaints/{complaint_id}/review",
        json={"new_status": "RESOLVED"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_COMPLAINT_TRANSITION"


@pytest.mark.asyncio
async def test_non_admin_cannot_review_a_complaint(client, seeded_collector):
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    file_resp = await client.post(
        "/api/v1/complaints",
        json={"target_type": "ward", "target_id": "WARD-1", "category": "X", "description": "y"},
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    complaint_id = file_resp.json()["complaint_id"]

    resp = await client.post(
        f"/api/v1/admin/complaints/{complaint_id}/review",
        json={"new_status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {collector_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_reviewing_unknown_complaint_returns_not_found(client, seeded_admin):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        "/api/v1/admin/complaints/does-not-exist/review",
        json={"new_status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "COMPLAINT_NOT_FOUND"
