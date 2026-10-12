import pytest


async def _login(client, username, password):
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_home_user_can_upload_a_photo_reference(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    response = await client.post(
        "/api/v1/ewaste/photos",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("remote.jpg", b"test-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 200, response.text
    photo_file_id = response.json()["photo_file_id"]
    assert photo_file_id.startswith("uploaded-photo:")


@pytest.mark.asyncio
async def test_photo_upload_rejects_non_image_files(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    response = await client.post(
        "/api/v1/ewaste/photos",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_PHOTO"