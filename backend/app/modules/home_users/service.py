from datetime import datetime, timezone

from app.core import audit
from app.core.errors import bad_request, not_found
from app.db.repositories import home_users_repo, users_repo, wards_repo
from app.modules.auth import service as auth_service
from app.modules.translation.service import SUPPORTED_LANGUAGES

DEFAULT_PREFERENCES = {
    "language": "eng_Latn",
    "collection_updates": True,
    "status_updates": True,
    "account_updates": True,
}


async def register(
    *,
    username: str,
    password: str,
    full_name: str,
    address: str,
    ward_id: str,
    household_lat: float,
    household_lng: float,
    upi_id: str | None,
) -> dict:
    ward = await wards_repo.find_by_ward_id(ward_id)
    if ward is None:
        raise not_found("WARD_NOT_FOUND", "No ward exists with this ward_id.")

    # Raises USERNAME_ALREADY_EXISTS (409) on duplicate — no silent no-op.
    user = await auth_service.create_user(username=username, password=password, role="HOME_USER")

    profile_doc = {
        "user_id": user["user_id"],
        "full_name": full_name,
        "address": address,
        "ward_id": ward_id,
        "household_lat": household_lat,
        "household_lng": household_lng,
        "upi_id": upi_id,
        "created_at": datetime.now(timezone.utc),
    }
    await home_users_repo.insert_profile(profile_doc)

    await audit.record(
        actor_id=user["user_id"],
        actor_role="HOME_USER",
        action="HOME_USER_REGISTERED",
        entity_type="home_user",
        entity_id=user["user_id"],
        details={"ward_id": ward_id},
    )

    return {"user": user, "profile": profile_doc}


async def get_profile(user_id: str) -> dict | None:
    profile = await home_users_repo.find_by_user_id(user_id)
    if profile is not None:
        profile.pop("_id", None)
        profile["preferences"] = {
            **DEFAULT_PREFERENCES,
            **profile.get("preferences", {}),
        }
    return profile


async def update_profile(*, user_id: str, full_name: str | None, address: str | None) -> dict:
    values = {}
    if full_name is not None:
        values["full_name"] = full_name.strip()
    if address is not None:
        values["address"] = address.strip()
    if not values or any(not value for value in values.values()):
        raise bad_request("INVALID_PROFILE", "At least one non-empty profile field is required.")

    profile = await home_users_repo.find_by_user_id(user_id)
    if profile is None:
        raise not_found("HOME_USER_PROFILE_NOT_FOUND", "No home-user profile found for this account.")
    await home_users_repo.update_profile(user_id, values)
    updated = await get_profile(user_id)
    return updated


async def update_preferences(
    *,
    user_id: str,
    language: str | None,
    collection_updates: bool | None,
    status_updates: bool | None,
    account_updates: bool | None,
) -> dict:
    values = {
        key: value
        for key, value in {
            "language": language,
            "collection_updates": collection_updates,
            "status_updates": status_updates,
            "account_updates": account_updates,
        }.items()
        if value is not None
    }
    if not values:
        raise bad_request("INVALID_PREFERENCES", "At least one preference is required.")
    if language is not None and language not in SUPPORTED_LANGUAGES:
        raise bad_request("UNSUPPORTED_LANGUAGE", "The selected language is not supported.")

    profile = await home_users_repo.find_by_user_id(user_id)
    if profile is None:
        raise not_found("HOME_USER_PROFILE_NOT_FOUND", "No home-user profile found for this account.")
    await home_users_repo.update_preferences(user_id, values)
    return await get_profile(user_id)


async def deactivate_account(current_user: dict) -> None:
    profile = await home_users_repo.find_by_user_id(current_user["user_id"])
    if profile is None:
        raise not_found("HOME_USER_PROFILE_NOT_FOUND", "No home-user profile found for this account.")
    await users_repo.deactivate(current_user["user_id"])
    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="ACCOUNT_DEACTIVATED",
        entity_type="user",
        entity_id=current_user["user_id"],
    )
