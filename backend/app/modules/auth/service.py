from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.errors import account_disabled, conflict, invalid_credentials, invalid_token
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.repositories import users_repo


async def login(username: str, password: str) -> dict:
    user = await users_repo.find_by_username(username)

    # Deliberately identical error whether the username doesn't exist or the
    # password is wrong (Section 6 of the Phase 1 plan — no enumeration).
    if user is None or not verify_password(password, user["password_hash"]):
        raise invalid_credentials()

    if user.get("status") != "ACTIVE":
        raise account_disabled()

    access_token = create_access_token(user_id=user["user_id"], role=user["role"])
    refresh_token = create_refresh_token(user_id=user["user_id"])
    await users_repo.set_refresh_token_hash(user["user_id"], hash_refresh_token(refresh_token))

    await audit.record(
        actor_id=user["user_id"],
        actor_role=user["role"],
        action="LOGIN",
        entity_type="user",
        entity_id=user["user_id"],
    )

    return {"access_token": access_token, "refresh_token": refresh_token, "role": user["role"]}


async def refresh(refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise invalid_token() from exc

    user = await users_repo.find_by_id(payload.get("sub"))
    if user is None or user.get("status") != "ACTIVE":
        raise invalid_token()

    stored_hash = user.get("refresh_token_hash")
    if stored_hash is None or stored_hash != hash_refresh_token(refresh_token):
        # Covers both "never logged in" and "already logged out" cases.
        raise invalid_token()

    new_access_token = create_access_token(user_id=user["user_id"], role=user["role"])
    return {"access_token": new_access_token}


async def logout(user: dict) -> None:
    await users_repo.set_refresh_token_hash(user["user_id"], None)
    await audit.record(
        actor_id=user["user_id"],
        actor_role=user["role"],
        action="LOGOUT",
        entity_type="user",
        entity_id=user["user_id"],
    )


async def create_user(*, username: str, password: str, role: str) -> dict:
    """Shared user-creation path for Phase 2+ modules (home-user
    self-registration, admin-created collector accounts). Unlike
    create_user_for_seeding (below), this always raises on a duplicate
    username instead of silently returning the existing record — a real
    registration/admin-creation call must not silently no-op."""
    user_doc = {
        "user_id": str(uuid4()),
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "status": "ACTIVE",
        "refresh_token_hash": None,
    }
    try:
        await users_repo.insert_user(user_doc)
    except DuplicateKeyError as exc:
        raise conflict("USERNAME_ALREADY_EXISTS", "This username is already taken.") from exc
    return user_doc


async def create_user_for_seeding(*, username: str, password: str, role: str) -> dict:
    """Used only by scripts/seed_admin.py in Phase 1. No API endpoint calls
    this — there is no self-registration route for any role yet."""
    existing = await users_repo.find_by_username(username)
    if existing is not None:
        return existing

    user_doc = {
        "user_id": str(uuid4()),
        "username": username,
        "password_hash": hash_password(password),
        "role": role,
        "status": "ACTIVE",
        "refresh_token_hash": None,
    }
    await users_repo.insert_user(user_doc)
    return user_doc
