"""
The one genuinely cross-cutting piece of Phase 7: a dashboard summary that
aggregates counts across many collections. Everything else admin-facing
lives colocated in its own owning domain module (matching the real
precedent Phase 5/6 already established — /admin/rrr-centres in
rrr_centres, /admin/recyclers in recyclers, /admin/collectors in
collectors — not the Phase-0 doc's original single-module sketch). A
dashboard summary has no single owning domain, so it lives here.

Read-only. No state changes, no idempotency key (not a state-changing
endpoint).
"""
from app.db.mongo import get_db
from app.db.repositories import users_repo


async def get_dashboard_summary() -> dict:
    db = get_db()

    users_by_role = {}
    for role in ("HOME_USER", "COLLECTOR", "RRR_CENTER", "RECYCLER", "GOVERNMENT_ADMIN"):
        users_by_role[role] = await users_repo.count_by_role(role)

    async def count_by_status(collection_name: str) -> dict[str, int]:
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        result: dict[str, int] = {}
        async for row in db[collection_name].aggregate(pipeline):
            result[row["_id"] or "UNKNOWN"] = row["count"]
        return result

    return {
        "users_by_role": users_by_role,
        "wards_count": await db.wards.count_documents({}),
        "rrr_centres_by_status": await count_by_status("rrr_centres"),
        "recyclers_by_status": await count_by_status("recyclers"),
        "submissions_by_status": await count_by_status("e_waste_submissions"),
        "lots_by_status": await count_by_status("lots"),
        "bids_by_status": await count_by_status("bids"),
        "complaints_by_status": await count_by_status("complaints"),
        "flagged_submissions_count": await db.e_waste_submissions.count_documents(
            {"status": "FLAGGED_FOR_REVIEW"}
        ),
    }
