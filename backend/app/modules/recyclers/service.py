"""
Recycler registration (self-service) + government approval — mirrors
app/modules/rrr_centres/service.py almost exactly, since the architecture
groups RRR/recycler approval under one permission-matrix line ("Approve
RRR / recycler registration"). No ward linkage here: recyclers are not
ward-scoped anywhere in the architecture — an approved recycler can browse
and bid on any LISTED_FOR_BIDDING lot regardless of ward.
"""
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.db.repositories import recyclers_repo, users_repo
from app.modules.auth import service as auth_service


async def register(*, username: str, password: str, company_name: str) -> dict:
    user = await auth_service.create_user(username=username, password=password, role="RECYCLER")

    profile_doc = {
        "user_id": user["user_id"],
        "license_id": username,
        "company_name": company_name,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await recyclers_repo.insert_profile(profile_doc)
    except DuplicateKeyError as exc:
        await users_repo.delete_user(user["user_id"])
        raise conflict("LICENSE_ID_ALREADY_EXISTS", "This license ID is already registered.") from exc
    except Exception:
        await users_repo.delete_user(user["user_id"])
        raise

    await audit.record(
        actor_id=user["user_id"],
        actor_role="RECYCLER",
        action="RECYCLER_REGISTERED",
        entity_type="recycler",
        entity_id=user["user_id"],
        details={"license_id": username},
    )

    return {"user": user, "profile": profile_doc}


async def get_profile(user_id: str) -> dict | None:
    profile = await recyclers_repo.find_by_user_id(user_id)
    if profile is not None:
        profile.pop("_id", None)
    return profile


async def require_approved_recycler(current_user: dict) -> dict:
    """Every privileged recycler action (place/cancel a bid) calls this
    first. Raises a specific, structured error rather than a generic 403
    so the client can distinguish "no profile" from "still pending" from
    "rejected" — same principle as require_approved_rrr()."""
    profile = await recyclers_repo.find_by_user_id(current_user["user_id"])
    if profile is None:
        raise not_found("RECYCLER_PROFILE_NOT_FOUND", "No recycler profile found for this account.")
    if profile["status"] != "APPROVED":
        raise forbidden(
            "RECYCLER_NOT_APPROVED",
            f"This recycler account is not yet approved (status: {profile['status']}).",
        )
    return profile


async def list_all_for_admin(status: str | None = None) -> list[dict]:
    profiles = await recyclers_repo.list_all(status=status)
    result = []
    for p in profiles:
        p.pop("_id", None)
        user = await users_repo.find_by_id(p["user_id"])
        result.append({**p, "username": user["username"] if user else None})
    return result


async def approve(*, user_id: str, actor: dict) -> dict:
    profile = await recyclers_repo.find_by_user_id(user_id)
    if profile is None:
        raise not_found("RECYCLER_PROFILE_NOT_FOUND", "No recycler profile found for this account.")
    if profile["status"] != "PENDING":
        raise bad_request("RECYCLER_NOT_PENDING", f"This recycler is not pending (status: {profile['status']}).")

    await recyclers_repo.update_status(user_id, "APPROVED")

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="RECYCLER_APPROVED",
        entity_type="recycler",
        entity_id=user_id,
        details={"license_id": profile["license_id"]},
    )
    profile["status"] = "APPROVED"
    profile.pop("_id", None)
    return profile


async def reject(*, user_id: str, actor: dict) -> dict:
    profile = await recyclers_repo.find_by_user_id(user_id)
    if profile is None:
        raise not_found("RECYCLER_PROFILE_NOT_FOUND", "No recycler profile found for this account.")
    if profile["status"] != "PENDING":
        raise bad_request("RECYCLER_NOT_PENDING", f"This recycler is not pending (status: {profile['status']}).")

    await recyclers_repo.update_status(user_id, "REJECTED")

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="RECYCLER_REJECTED",
        entity_type="recycler",
        entity_id=user_id,
        details={"license_id": profile["license_id"]},
    )
    profile["status"] = "REJECTED"
    profile.pop("_id", None)
    return profile
