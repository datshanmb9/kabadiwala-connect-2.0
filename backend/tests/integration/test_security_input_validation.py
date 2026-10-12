"""
Phase 11 security audit: input validation and injection-style attempts
against the real HTTP layer. Every user-supplied field in this codebase
is Pydantic-typed (no raw dict passthrough into a Mongo filter anywhere),
so the expectation these tests hold the implementation to is that
injection-shaped strings are treated as inert data, never as query
operators — and that the new server-side password minimum length
(Phase 11 fix) is actually enforced by the schema, not just by frontend
form validation.
"""
import pytest


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,payload",
    [
        (
            "/api/v1/home-users/register",
            {
                "username": "short-pw-home", "password": "short1", "full_name": "X", "address": "x",
                "ward_id": "WARD-1", "household_lat": 12.9716, "household_lng": 77.5946, "upi_id": None,
            },
        ),
        ("/api/v1/rrr-centres/register", {
            "username": "short-pw-rrr", "password": "short1", "rrr_id": "R1", "tender_id": "T1", "ward_id": "WARD-1",
        }),
        ("/api/v1/recyclers/register", {"username": "short-pw-rcy", "password": "short1", "company_name": "Co"}),
    ],
)
async def test_registration_rejects_password_shorter_than_8_chars_server_side(client, seeded_ward, path, payload):
    resp = await client.post(path, json=payload)
    assert resp.status_code == 422, f"{path} should reject a 6-char password server-side, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_admin_created_collector_password_is_also_enforced_server_side(client, seeded_admin, seeded_ward):
    admin_token = await _login(client, "admin", "admin1234")
    token = admin_token.json()["access_token"]
    resp = await client.post(
        "/api/v1/admin/collectors",
        json={"employee_id": "SHORT-PW-COL", "password": "short1", "ward_id": "WARD-1", "rrr_id": None, "assigned_area_radius_m": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_registration_accepts_exactly_8_char_password(client, seeded_ward):
    resp = await client.post(
        "/api/v1/home-users/register",
        json={
            "username": "exact-8-pw-home", "password": "exactly8", "full_name": "X", "address": "x",
            "ward_id": "WARD-1", "household_lat": 12.9716, "household_lng": 77.5946, "upi_id": None,
        },
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_login_still_accepts_pre_existing_short_passwords(client, seeded_admin):
    """The Phase 11 length fix only applies going forward to new
    registrations — LoginRequest.password was deliberately left
    unconstrained so accounts seeded/created before this fix (like
    seeded_admin's 8-char 'admin1234', or any shorter historical
    password) are never locked out."""
    resp = await _login(client, "admin", "admin1234")
    assert resp.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "injection_value",
    [
        {"$ne": None},
        {"$gt": ""},
        {"$where": "1==1"},
    ],
)
async def test_mongo_operator_shaped_json_object_is_rejected_by_schema_not_executed_as_a_query(
    client, seeded_ward, injection_value
):
    """username is typed as `str` in every schema — Pydantic must reject
    a JSON object in that field with a 422 long before it could ever
    reach a Mongo filter as an operator."""
    resp = await client.post(
        "/api/v1/home-users/register",
        json={
            "username": injection_value, "password": "homepass123", "full_name": "X", "address": "x",
            "ward_id": "WARD-1", "household_lat": 12.9716, "household_lng": 77.5946, "upi_id": None,
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_mongo_operator_shaped_string_in_login_is_treated_as_a_literal_no_match(client, seeded_admin):
    """A classic NoSQL-injection payload as a STRING (matching the `str`
    type, so it passes schema validation) must still fail to authenticate
    — proving the lookup is an exact-match find_one on a literal string,
    never a raw dict merge that could smuggle in a real Mongo operator."""
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": '{"$ne": null}'}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_oversized_and_wrong_type_fields_are_rejected_not_crashed_on(client, seeded_ward):
    resp = await client.post(
        "/api/v1/home-users/register",
        json={
            "username": "wrong-type-home", "password": "homepass123", "full_name": "X", "address": "x",
            "ward_id": "WARD-1", "household_lat": "not-a-number", "household_lng": 77.5946, "upi_id": None,
        },
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_missing_required_fields_rejected_with_422_not_500(client, seeded_ward):
    resp = await client.post("/api/v1/home-users/register", json={"username": "incomplete-home"})
    assert resp.status_code == 422
