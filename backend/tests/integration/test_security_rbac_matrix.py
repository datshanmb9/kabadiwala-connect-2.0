"""
Phase 11 security audit: a systematic RBAC sweep, distinct from the
per-endpoint role checks already scattered across each phase's own test
file and from test_cross_role_isolation.py's admin-only sweep. This file
proves two additional things those don't already cover on their own:
(1) every one of the 5 authenticated roles, tried against a
role-restricted endpoint that ISN'T theirs, is rejected — not just
"non-admin vs admin-only" — and (2) a request with NO token at all is
rejected (401), never silently treated as any role.
"""
import pytest


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_every_role_is_rejected_from_every_other_roles_restricted_endpoint(
    client, seeded_admin, seeded_home_user, seeded_collector, seeded_rrr_center, seeded_approved_recycler
):
    admin_token = await _login(client, "admin", "admin1234")
    home_token = await _login(client, "home-user-1", "homepass123")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    recycler_token = await _login(client, "demo-recycler-1", "recyclerpass123")

    # (endpoint, method, the ONLY token that should be allowed through)
    role_restricted_endpoints = [
        ("GET", "/api/v1/collectors/me", collector_token),
        ("GET", "/api/v1/rrr-centres/me", rrr_token),
        ("GET", "/api/v1/recyclers/me", recycler_token),
        ("GET", "/api/v1/home-users/me", home_token),
        ("GET", "/api/v1/admin/collectors", admin_token),
        ("GET", "/api/v1/lots", rrr_token),
        ("GET", "/api/v1/bids/mine", recycler_token),
    ]
    all_tokens = {
        "HOME_USER": home_token,
        "COLLECTOR": collector_token,
        "RRR_CENTER": rrr_token,
        "RECYCLER": recycler_token,
        "GOVERNMENT_ADMIN": admin_token,
    }

    for method, path, allowed_token in role_restricted_endpoints:
        for role_name, token in all_tokens.items():
            resp = await client.request(method, path, headers={"Authorization": f"Bearer {token}"})
            if token == allowed_token:
                assert resp.status_code in (200, 404), f"{role_name} on {path} should be let in: {resp.text}"
            else:
                assert resp.status_code == 403, f"{role_name} on {path} should be rejected, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_no_token_at_all_is_rejected_as_unauthenticated_not_as_any_default_role(client, seeded_admin):
    no_auth_calls = [
        ("GET", "/api/v1/admin/lots"),
        ("GET", "/api/v1/lots"),
        ("GET", "/api/v1/bids/mine"),
        ("GET", "/api/v1/home-users/me"),
        ("GET", "/api/v1/collectors/me"),
    ]
    for method, path in no_auth_calls:
        resp = await client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} with no token should be 401, got {resp.status_code}"


@pytest.mark.asyncio
async def test_malformed_or_garbage_bearer_token_is_rejected_not_crashed_on(client, seeded_admin):
    garbage_tokens = ["not-a-jwt-at-all", "", "a.b.c", "Bearer", "null", "undefined"]
    for garbage in garbage_tokens:
        resp = await client.get("/api/v1/admin/lots", headers={"Authorization": f"Bearer {garbage}"})
        assert resp.status_code == 401, f"garbage token {garbage!r} should be 401, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_refresh_token_cannot_be_used_directly_as_an_access_token(client, seeded_admin):
    """JWT type-confusion check: auth/service.py's decode_token(expected_type=...)
    must actually be enforced, not just present in the code but unused."""
    login_resp = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.get("/api/v1/admin/lots", headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401, f"a refresh token used as an access token must be rejected, got {resp.status_code}"
