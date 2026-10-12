"""
Requires the full stack (fastapi, motor, mongomock-motor, httpx, passlib,
python-jose). Run with: pytest tests/integration/test_auth_api.py
"""
import pytest


@pytest.mark.asyncio
async def test_login_success(client, seeded_admin):
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "GOVERNMENT_ADMIN"
    assert "access_token" in body and "refresh_token" in body


@pytest.mark.asyncio
async def test_login_wrong_password(client, seeded_admin):
    resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_username_returns_same_error_as_wrong_password(client, seeded_admin):
    """No username enumeration: both cases must be indistinguishable."""
    resp_unknown = await client.post("/api/v1/auth/login", json={"username": "nobody", "password": "whatever"})
    resp_wrong_pw = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})

    assert resp_unknown.status_code == resp_wrong_pw.status_code == 401
    assert resp_unknown.json()["error_code"] == resp_wrong_pw.json()["error_code"] == "INVALID_CREDENTIALS"
    assert resp_unknown.json()["message"] == resp_wrong_pw.json()["message"]


@pytest.mark.asyncio
async def test_me_returns_correct_role(client, seeded_admin):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    access_token = login_resp.json()["access_token"]

    me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "GOVERNMENT_ADMIN"


@pytest.mark.asyncio
async def test_me_rejects_missing_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_me_rejects_tampered_token(client, seeded_admin):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")

    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_gets_403_on_audit_logs(client, seeded_recycler):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "RCY-001", "password": "recyclerpass1"})
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_admin_gets_200_on_audit_logs(client, seeded_admin):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_login_creates_audit_log_entry(client, seeded_admin):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    token = login_resp.json()["access_token"]

    logs_resp = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {token}"})
    actions = [log["action"] for log in logs_resp.json()["logs"]]
    assert "LOGIN" in actions


@pytest.mark.asyncio
async def test_refresh_issues_new_access_token(client, seeded_admin):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()


@pytest.mark.asyncio
async def test_refresh_rejected_after_logout(client, seeded_admin):
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    access_token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout_resp.status_code == 200

    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["error_code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_health_endpoint_requires_no_auth(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
