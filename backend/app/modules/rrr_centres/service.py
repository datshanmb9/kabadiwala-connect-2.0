"""
RRR Centre registration (self-service, like home_users) + government
approval (admin-only, like the collector-assignment write path). Unlike
collectors, RRR centres DO self-register — the permission matrix in the
architecture doc explicitly lists "Approve RRR / recycler registration" as
a GOVERNMENT_ADMIN action, implying there is something submitted to
approve. A registered-but-not-yet-approved account can still log in (it's
ACTIVE at the users-collection level) but every privileged RRR action
must pass through require_approved_rrr() below — role alone is never
sufficient, same principle as every other ownership/status gate in this
codebase.
"""
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.db.repositories import rrr_centres_repo, users_repo, wards_repo
from app.modules.auth import service as auth_service


async def register(
    *,
    username: str,
    password: str,
    rrr_id: str,
    tender_id: str,
    ward_id: str,
    licence_doc_ref: str | None,
) -> dict:
    ward = await wards_repo.find_by_ward_id(ward_id)
    if ward is None:
        raise not_found("WARD_NOT_FOUND", "No ward exists with this ward_id.")

    user = await auth_service.create_user(username=username, password=password, role="RRR_CENTER")

    profile_doc = {
        "user_id": user["user_id"],
        "rrr_id": rrr_id,
        "tender_id": tender_id,
        "ward_id": ward_id,
        "licence_doc_ref": licence_doc_ref,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await rrr_centres_repo.insert_profile(profile_doc)
    except DuplicateKeyError as exc:
        raise conflict("RRR_ID_OR_TENDER_ID_ALREADY_EXISTS", "This RRR ID or tender ID is already registered.") from exc

    await audit.record(
        actor_id=user["user_id"],
        actor_role="RRR_CENTER",
        action="RRR_CENTER_REGISTERED",
        entity_type="rrr_centre",
        entity_id=user["user_id"],
        details={"rrr_id": rrr_id, "ward_id": ward_id},
    )

    return {"user": user, "profile": profile_doc}


async def get_profile(user_id: str) -> dict | None:
    profile = await rrr_centres_repo.find_by_user_id(user_id)
    if profile is not None:
        profile.pop("_id", None)
    return profile


async def require_approved_rrr(current_user: dict) -> dict:
    """Every privileged RRR action (receive, classify, create/publish a
    lot) calls this first. Raises a specific, structured error rather
    than a generic 403 so the client can distinguish "no profile" from
    "still pending" from "rejected"."""
    profile = await rrr_centres_repo.find_by_user_id(current_user["user_id"])
    if profile is None:
        raise not_found("RRR_CENTRE_PROFILE_NOT_FOUND", "No RRR centre profile found for this account.")
    if profile["status"] != "APPROVED":
        raise forbidden(
            "RRR_NOT_APPROVED",
            f"This RRR centre account is not yet approved (status: {profile['status']}).",
        )
    return profile


async def list_all_for_admin(status: str | None = None) -> list[dict]:
    profiles = await rrr_centres_repo.list_all(status=status)
    result = []
    for p in profiles:
        p.pop("_id", None)
        user = await users_repo.find_by_id(p["user_id"])
        result.append({**p, "username": user["username"] if user else None})
    return result


async def approve(*, user_id: str, actor: dict) -> dict:
    profile = await rrr_centres_repo.find_by_user_id(user_id)
    if profile is None:
        raise not_found("RRR_CENTRE_PROFILE_NOT_FOUND", "No RRR centre profile found for this account.")
    if profile["status"] != "PENDING":
        raise bad_request("RRR_NOT_PENDING", f"This RRR centre is not pending (status: {profile['status']}).")

    linked = await wards_repo.assign_rrr_centre(profile["ward_id"], profile["rrr_id"])
    if not linked:
        raise conflict(
            "WARD_ALREADY_HAS_RRR_CENTRE",
            "The claimed ward already has an approved RRR centre assigned.",
        )

    await rrr_centres_repo.update_status(user_id, "APPROVED")

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="RRR_CENTER_APPROVED",
        entity_type="rrr_centre",
        entity_id=user_id,
        details={"rrr_id": profile["rrr_id"], "ward_id": profile["ward_id"]},
    )
    profile["status"] = "APPROVED"
    profile.pop("_id", None)
    return profile


async def reject(*, user_id: str, actor: dict) -> dict:
    profile = await rrr_centres_repo.find_by_user_id(user_id)
    if profile is None:
        raise not_found("RRR_CENTRE_PROFILE_NOT_FOUND", "No RRR centre profile found for this account.")
    if profile["status"] != "PENDING":
        raise bad_request("RRR_NOT_PENDING", f"This RRR centre is not pending (status: {profile['status']}).")

    await rrr_centres_repo.update_status(user_id, "REJECTED")

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="RRR_CENTER_REJECTED",
        entity_type="rrr_centre",
        entity_id=user_id,
        details={"rrr_id": profile["rrr_id"]},
    )
    profile["status"] = "REJECTED"
    profile.pop("_id", None)
    return profile
