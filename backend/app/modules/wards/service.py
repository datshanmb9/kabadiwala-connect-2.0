from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.core import audit
from app.core.errors import conflict
from app.db.repositories import wards_repo


async def create_ward(*, ward_id: str, name: str, actor: dict) -> dict:
    doc = {
        "ward_id": ward_id,
        "name": name,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await wards_repo.insert_ward(doc)
    except DuplicateKeyError as exc:
        raise conflict("WARD_ALREADY_EXISTS", "A ward with this ward_id already exists.") from exc

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="WARD_CREATED",
        entity_type="ward",
        entity_id=ward_id,
        details={"name": name},
    )
    return doc


async def list_wards() -> list[dict]:
    wards = await wards_repo.list_wards()
    for w in wards:
        w.pop("_id", None)
    return wards
