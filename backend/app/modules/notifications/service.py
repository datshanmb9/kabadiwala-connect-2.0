from datetime import datetime, timezone
from uuid import uuid4

from app.core.errors import not_found
from app.db.repositories import home_users_repo, notifications_repo

COLLECTION_REQUEST_CREATED = "COLLECTION_REQUEST_CREATED"
COLLECTION_REQUEST_ACCEPTED = "COLLECTION_REQUEST_ACCEPTED"
COLLECTION_COMPLETED = "COLLECTION_COMPLETED"
COLLECTION_STATUS_CHANGED = "COLLECTION_STATUS_CHANGED"
# Sent to recyclers when a lot owner (RRR centre or collector) accepts a
# bid — the winner gets BID_ACCEPTED, every other PLACED bidder on that
# lot gets BID_REJECTED. Not in _PREFERENCE_BY_TYPE below: recyclers have
# no notification-preferences document (that concept exists only for
# home_users today), so create_notification's preference gate is
# correctly a no-op for these — see its docstring/body.
BID_ACCEPTED = "BID_ACCEPTED"
BID_REJECTED = "BID_REJECTED"

_PREFERENCE_BY_TYPE = {
    COLLECTION_REQUEST_CREATED: "collection_updates",
    COLLECTION_REQUEST_ACCEPTED: "status_updates",
    COLLECTION_COMPLETED: "status_updates",
    COLLECTION_STATUS_CHANGED: "status_updates",
    "REWARD_CREDITED": "account_updates",
    "REWARD_REDEMPTION_SUCCEEDED": "account_updates",
    "REWARD_REDEMPTION_FAILED": "account_updates",
}


def _clean(document: dict) -> dict:
    document.pop("_id", None)
    return document


async def create_notification(
    *,
    user_id: str,
    event_key: str,
    notification_type: str,
    title_key: str,
    message_key: str,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    metadata: dict | None = None,
) -> dict | None:
    profile = await home_users_repo.find_by_user_id(user_id)
    preferences = (profile or {}).get("preferences", {})
    preference_key = _PREFERENCE_BY_TYPE.get(notification_type)
    if preference_key is not None and preferences.get(preference_key, True) is False:
        return None

    document = {
        "notification_id": str(uuid4()),
        "user_id": user_id,
        "event_key": event_key,
        "type": notification_type,
        "title_key": title_key,
        "message_key": message_key,
        "related_entity_type": related_entity_type,
        "related_entity_id": related_entity_id,
        "read": False,
        "created_at": datetime.now(timezone.utc),
        "read_at": None,
        "metadata": metadata or {},
    }
    inserted = await notifications_repo.insert_notification(document)
    return document if inserted else None


async def list_notifications(user_id: str, *, limit: int, offset: int) -> dict:
    documents = await notifications_repo.list_for_user(user_id, limit=limit, offset=offset)
    for document in documents:
        _clean(document)
    return {
        "notifications": documents,
        "unread_count": await notifications_repo.count_unread(user_id),
        "has_more": len(documents) == limit,
    }


async def unread_count(user_id: str) -> int:
    return await notifications_repo.count_unread(user_id)


async def mark_read(*, user_id: str, notification_id: str) -> dict:
    document = await notifications_repo.mark_read(
        user_id,
        notification_id,
        datetime.now(timezone.utc),
    )
    if document is None:
        raise not_found("NOTIFICATION_NOT_FOUND", "No notification exists for this account.")
    return _clean(document)


async def mark_all_read(user_id: str) -> dict:
    marked_count = await notifications_repo.mark_all_read(user_id, datetime.now(timezone.utc))
    return {"marked_count": marked_count, "unread_count": 0}
