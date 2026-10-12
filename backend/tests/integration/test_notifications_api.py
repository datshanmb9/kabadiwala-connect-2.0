import pytest

from app.modules.ewaste import service as ewaste_service
from app.modules.home_users import service as home_users_service
from app.modules.notifications import service as notifications_service


async def _login(client, username, password):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_submission_creation_persists_user_notification(client, seeded_home_user):
    result = await ewaste_service.create_submission(
        current_user=seeded_home_user,
        ward_id="WARD-1",
        photo_file_id="notification-photo",
        home_lat=12.9716,
        home_lng=77.5946,
        home_ts=None,
        idempotency_key="notification-submit-1",
    )
    token = await _login(client, "home-user-1", "homepass123")

    response = await client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["unread_count"] == 1
    notification = response.json()["notifications"][0]
    assert notification["type"] == "COLLECTION_REQUEST_CREATED"
    assert notification["related_entity_id"] == result["submission_id"]


@pytest.mark.asyncio
async def test_notifications_are_user_scoped(client, seeded_home_user, seeded_ward):
    await home_users_service.register(
        username="home-user-2",
        password="homepass123",
        full_name="Second User",
        address="Second Address",
        ward_id="WARD-1",
        household_lat=12.9716,
        household_lng=77.5946,
        upi_id=None,
    )
    await notifications_service.create_notification(
        user_id=seeded_home_user["user_id"],
        event_key="account:scoped-test",
        notification_type="ACCOUNT_UPDATE",
        title_key="Profile",
        message_key="Profile updated successfully.",
    )
    other_token = await _login(client, "home-user-2", "homepass123")

    response = await client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 200
    assert response.json()["notifications"] == []


@pytest.mark.asyncio
async def test_mark_one_and_all_read_update_unread_count(client, seeded_home_user):
    first = await notifications_service.create_notification(
        user_id=seeded_home_user["user_id"],
        event_key="read-test-1",
        notification_type="ACCOUNT_UPDATE",
        title_key="Profile",
        message_key="Profile updated successfully.",
    )
    await notifications_service.create_notification(
        user_id=seeded_home_user["user_id"],
        event_key="read-test-2",
        notification_type="IMPORTANT_SYSTEM_UPDATE",
        title_key="Settings",
        message_key="Important account updates",
    )
    token = await _login(client, "home-user-1", "homepass123")

    one = await client.patch(
        f"/api/v1/notifications/{first['notification_id']}/read",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert one.status_code == 200
    assert one.json()["read"] is True

    count = await client.get(
        "/api/v1/notifications/unread-count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert count.json()["unread_count"] == 1

    all_read = await client.patch(
        "/api/v1/notifications/read-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert all_read.status_code == 200
    assert all_read.json()["marked_count"] == 1
    assert all_read.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_duplicate_event_is_ignored_and_missing_read_is_404(client, seeded_home_user):
    first = await notifications_service.create_notification(
        user_id=seeded_home_user["user_id"],
        event_key="duplicate-event",
        notification_type="ACCOUNT_UPDATE",
        title_key="Profile",
        message_key="Profile updated successfully.",
    )
    second = await notifications_service.create_notification(
        user_id=seeded_home_user["user_id"],
        event_key="duplicate-event",
        notification_type="ACCOUNT_UPDATE",
        title_key="Profile",
        message_key="Profile updated successfully.",
    )
    assert first is not None
    assert second is None
    token = await _login(client, "home-user-1", "homepass123")

    missing = await client.patch(
        "/api/v1/notifications/not-found/read",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "NOTIFICATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_status_preference_suppresses_status_notification(client, seeded_home_user):
    await home_users_service.update_preferences(
        user_id=seeded_home_user["user_id"],
        language=None,
        collection_updates=None,
        status_updates=False,
        account_updates=None,
    )
    created = await notifications_service.create_notification(
        user_id=seeded_home_user["user_id"],
        event_key="preference-filtered-status",
        notification_type=notifications_service.COLLECTION_COMPLETED,
        title_key="Collection completed",
        message_key="Your e-waste collection has been completed.",
    )
    assert created is None


@pytest.mark.asyncio
async def test_recycler_can_access_their_own_notifications(client, seeded_recycler):
    """Widened alongside the collector-selects-recycler workflow: RECYCLER
    (and COLLECTOR) now receive BID_ACCEPTED/BID_REJECTED notifications and
    must be able to read their own, same as HOME_USER always could. Scoping
    is unchanged — service.list_notifications always keys off the caller's
    own current_user["user_id"], never a client-supplied one."""
    token = await _login(client, "RCY-001", "recyclerpass1")
    response = await client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["notifications"] == []


@pytest.mark.asyncio
async def test_role_with_no_notification_use_case_cannot_access_notifications(client, seeded_rrr_center):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    response = await client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_ROLE"
