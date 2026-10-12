"""
Account creation is admin-only (Section 5 of the architecture doc): there
is no collector self-registration endpoint anywhere in this module, and the
collector-facing router (see router.py) exposes only a read-only `/me`.
"""
from datetime import datetime, timezone

from app.core import audit
from app.core.errors import bad_request, not_found
from app.db.repositories import collectors_repo, users_repo, wards_repo
from app.modules.auth import service as auth_service


async def create_collector(
    *,
    employee_id: str,
    password: str,
    ward_id: str,
    rrr_id: str | None,
    assigned_area_radius_m: float | None,
    actor: dict,
) -> dict:
    ward = await wards_repo.find_by_ward_id(ward_id)
    if ward is None:
        raise not_found("WARD_NOT_FOUND", "No ward exists with this ward_id.")

    # username = employee_id; raises EMPLOYEE_ID_ALREADY... via the shared
    # USERNAME_ALREADY_EXISTS conflict if this employee_id is already taken.
    user = await auth_service.create_user(username=employee_id, password=password, role="COLLECTOR")

    profile_doc = {
        "user_id": user["user_id"],
        "employee_id": employee_id,
        "ward_id": ward_id,
        "rrr_id": rrr_id,
        "assigned_area_radius_m": assigned_area_radius_m,
        "created_by_admin_id": actor["user_id"],
        "created_at": datetime.now(timezone.utc),
    }
    await collectors_repo.insert_profile(profile_doc)

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="COLLECTOR_CREATED",
        entity_type="collector",
        entity_id=user["user_id"],
        details={"employee_id": employee_id, "ward_id": ward_id},
    )

    return {"user": user, "profile": profile_doc}


async def get_profile(user_id: str) -> dict | None:
    profile = await collectors_repo.find_by_user_id(user_id)
    if profile is not None:
        profile.pop("_id", None)
    return profile


async def list_all_for_admin() -> list[dict]:
    profiles = await collectors_repo.list_all()
    result = []
    for p in profiles:
        p.pop("_id", None)
        user = await users_repo.find_by_id(p["user_id"])
        result.append({**p, "status": user["status"] if user else "UNKNOWN"})
    return result


async def update_assignment(
    *,
    user_id: str,
    ward_id: str | None,
    rrr_id: str | None,
    assigned_area_radius_m: float | None,
    actor: dict,
) -> dict:
    profile = await collectors_repo.find_by_user_id(user_id)
    if profile is None:
        raise not_found("COLLECTOR_PROFILE_NOT_FOUND", "No collector profile found for this account.")

    if ward_id is not None:
        ward = await wards_repo.find_by_ward_id(ward_id)
        if ward is None:
            raise not_found("WARD_NOT_FOUND", "No ward exists with this ward_id.")

    await collectors_repo.update_assignment(
        user_id, ward_id=ward_id, rrr_id=rrr_id, assigned_area_radius_m=assigned_area_radius_m
    )

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="COLLECTOR_ASSIGNMENT_UPDATED",
        entity_type="collector",
        entity_id=user_id,
        details={"ward_id": ward_id, "rrr_id": rrr_id, "assigned_area_radius_m": assigned_area_radius_m},
    )

    updated = await collectors_repo.find_by_user_id(user_id)
    updated.pop("_id", None)
    return updated


async def set_status(*, user_id: str, new_status: str, actor: dict) -> dict:
    if new_status not in ("ACTIVE", "DISABLED"):
        raise bad_request("INVALID_STATUS", "status must be ACTIVE or DISABLED.")

    profile = await collectors_repo.find_by_user_id(user_id)
    if profile is None:
        raise not_found("COLLECTOR_PROFILE_NOT_FOUND", "No collector profile found for this account.")

    await users_repo.update_status(user_id, new_status)

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="COLLECTOR_STATUS_CHANGED",
        entity_type="collector",
        entity_id=user_id,
        details={"employee_id": profile["employee_id"], "new_status": new_status},
    )

    profile.pop("_id", None)
    return {**profile, "status": new_status}
