"""
The single shared entry point every module calls to write an audit event.
Centralizing it here means logging can't be present in one module and
forgotten in another (the failure mode named in the architecture doc).
"""
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.db.repositories import audit_repo


async def record(
    *,
    actor_id: str | None,
    actor_role: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    await audit_repo.insert_log(
        {
            "log_id": str(uuid4()),
            "actor_id": actor_id,
            "actor_role": actor_role,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc),
        }
    )
