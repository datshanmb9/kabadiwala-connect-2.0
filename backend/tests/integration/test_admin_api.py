import pytest

from app.db.repositories import audit_repo

HOME_LAT = 12.9716
HOME_LNG = 77.5946
FAR_LAT = 13.0827
FAR_LNG = 80.2707


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_summary_reflects_real_counts(client, seeded_admin, seeded_collector, pending_recycler):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get(
        "/api/v1/admin/dashboard/summary", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()["summary"]
    assert summary["users_by_role"]["COLLECTOR"] == 1
    assert summary["users_by_role"]["GOVERNMENT_ADMIN"] == 1
    assert summary["recyclers_by_status"]["PENDING"] == 1
    assert summary["wards_count"] == 1


@pytest.mark.asyncio
async def test_non_admin_cannot_view_dashboard_summary(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.get("/api/v1/admin/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


# ---------------------------------------------------------------------------
# Collector admin management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_collectors(client, seeded_admin, seeded_collector):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get("/api/v1/admin/collectors", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    collectors = resp.json()["collectors"]
    assert len(collectors) == 1
    assert collectors[0]["employee_id"] == "EMP-001"
    assert "password" not in collectors[0] and "password_hash" not in collectors[0]


@pytest.mark.asyncio
async def test_non_admin_cannot_list_collectors(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.get("/api/v1/admin/collectors", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_admin_can_reassign_collector_ward_and_it_is_audited(
    client, seeded_admin, seeded_collector, other_ward, test_db
):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.patch(
        f"/api/v1/admin/collectors/{seeded_collector['user_id']}",
        json={"ward_id": "WARD-2"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["collector"]["ward_id"] == "WARD-2"

    logs = await audit_repo.list_logs(actor_role="GOVERNMENT_ADMIN", entity_type="collector")
    matching = [
        log
        for log in logs
        if log["entity_id"] == seeded_collector["user_id"] and log["action"] == "COLLECTOR_ASSIGNMENT_UPDATED"
    ]
    assert len(matching) == 1
    assert matching[0]["details"]["ward_id"] == "WARD-2"


@pytest.mark.asyncio
async def test_reassigning_to_unknown_ward_is_rejected(client, seeded_admin, seeded_collector):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.patch(
        f"/api/v1/admin/collectors/{seeded_collector['user_id']}",
        json={"ward_id": "NO-SUCH-WARD"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "WARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_non_admin_cannot_patch_a_collector(client, seeded_collector, other_ward):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.patch(
        f"/api/v1/admin/collectors/{seeded_collector['user_id']}",
        json={"ward_id": "WARD-2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_admin_can_disable_a_collector_and_it_is_audited_and_locks_login(
    client, seeded_admin, seeded_collector, test_db
):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        f"/api/v1/admin/collectors/{seeded_collector['user_id']}/status",
        json={"status": "DISABLED"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["collector"]["status"] == "DISABLED"

    logs = await audit_repo.list_logs(actor_role="GOVERNMENT_ADMIN", entity_type="collector")
    matching = [
        log
        for log in logs
        if log["entity_id"] == seeded_collector["user_id"] and log["action"] == "COLLECTOR_STATUS_CHANGED"
    ]
    assert len(matching) == 1
    assert matching[0]["details"]["new_status"] == "DISABLED"

    # Real enforcement, not cosmetic: a disabled account can no longer log in.
    login_resp = await client.post(
        "/api/v1/auth/login", json={"username": "EMP-001", "password": "collectorpass1"}
    )
    assert login_resp.status_code == 403
    assert login_resp.json()["error_code"] == "ACCOUNT_DISABLED"


@pytest.mark.asyncio
async def test_status_update_rejects_invalid_value(client, seeded_admin, seeded_collector):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.post(
        f"/api/v1/admin/collectors/{seeded_collector['user_id']}/status",
        json={"status": "NOT_A_REAL_STATUS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_STATUS"


# ---------------------------------------------------------------------------
# Submissions / handovers oversight (read-only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_all_submissions(client, seeded_admin, collected_submission):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get("/api/v1/admin/submissions", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert any(s["submission_id"] == collected_submission for s in resp.json()["submissions"])


@pytest.mark.asyncio
async def test_admin_can_filter_submissions_by_flagged_status(client, seeded_admin, seeded_home_user, seeded_collector):
    home_token = await _login(client, "home-user-1", "homepass123")
    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "p", "home_lat": HOME_LAT, "home_lng": HOME_LNG},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "admin-flag-submit"},
    )
    submission_id = submit_resp.json()["submission_id"]
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    handover_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p", "collector_lat": FAR_LAT, "collector_lng": FAR_LNG},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "admin-flag-handover"},
    )
    assert handover_resp.json()["status"] == "FLAGGED_FOR_REVIEW"

    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get(
        "/api/v1/admin/submissions?status=FLAGGED_FOR_REVIEW", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    ids = [s["submission_id"] for s in resp.json()["submissions"]]
    assert submission_id in ids

    handovers_resp = await client.get(
        "/api/v1/admin/handovers?verification_result=FLAGGED", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert handovers_resp.status_code == 200
    assert any(h["submission_id"] == submission_id for h in handovers_resp.json()["handovers"])


@pytest.mark.asyncio
async def test_non_admin_cannot_list_submissions_or_handovers(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp1 = await client.get("/api/v1/admin/submissions", headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 403
    resp2 = await client.get("/api/v1/admin/handovers", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 403


# ---------------------------------------------------------------------------
# Lots / bids oversight (read-only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_all_lots(client, seeded_admin, listed_lot):
    lot_id, _submission_id = listed_lot
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get("/api/v1/admin/lots", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert any(lot["lot_id"] == lot_id for lot in resp.json()["lots"])


@pytest.mark.asyncio
async def test_admin_can_filter_lots_by_status(client, seeded_admin, listed_lot):
    lot_id, _submission_id = listed_lot
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get(
        "/api/v1/admin/lots?status=LISTED_FOR_BIDDING", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert all(lot["status"] == "LISTED_FOR_BIDDING" for lot in resp.json()["lots"])
    assert any(lot["lot_id"] == lot_id for lot in resp.json()["lots"])


@pytest.mark.asyncio
async def test_admin_can_list_all_bids(client, seeded_admin, listed_lot, seeded_approved_recycler):
    lot_id, _submission_id = listed_lot
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")
    place_resp = await client.post(
        "/api/v1/bids",
        json={"lot_id": lot_id, "amount": "500.00"},
        headers={"Authorization": f"Bearer {recycler_token}", "Idempotency-Key": "admin-bid-1"},
    )
    assert place_resp.status_code == 200, place_resp.text
    bid_id = place_resp.json()["bid_id"]

    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get("/api/v1/admin/bids", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert any(b["bid_id"] == bid_id for b in resp.json()["bids"])


@pytest.mark.asyncio
async def test_non_admin_cannot_list_lots_or_bids_via_admin_routes(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp1 = await client.get("/api/v1/admin/lots", headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 403
    resp2 = await client.get("/api/v1/admin/bids", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 403


# ---------------------------------------------------------------------------
# Audit log filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_can_be_filtered_by_actor_role_and_entity_type(
    client, seeded_admin, seeded_collector, other_ward
):
    admin_token = await _login(client, "admin", "admin1234")
    await client.patch(
        f"/api/v1/admin/collectors/{seeded_collector['user_id']}",
        json={"ward_id": "WARD-2"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = await client.get(
        "/api/v1/audit-logs?actor_role=GOVERNMENT_ADMIN&entity_type=collector",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    assert len(logs) >= 1
    assert all(log["actor_role"] == "GOVERNMENT_ADMIN" and log["entity_type"] == "collector" for log in logs)


@pytest.mark.asyncio
async def test_audit_log_unfiltered_behavior_is_unchanged(client, seeded_admin, seeded_collector):
    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert "logs" in resp.json()
