"""
Single Motor client for the whole app. Index creation happens once at
startup (idempotent — create_index is a no-op if the index already exists
with the same spec), never on every request.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.database_url)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[settings.database_name]
    return _db


async def create_indexes() -> None:
    """Phase 1 scope: only the collections this phase actually writes to.
    Later phases add their own index calls in their own modules, called from
    the same startup hook, so index ownership stays next to the code that
    uses that collection."""
    db = get_db()

    await db.users.create_index("username", unique=True)
    await db.users.create_index("role")

    await db.audit_logs.create_index([("entity_type", 1), ("entity_id", 1)])
    await db.audit_logs.create_index([("timestamp", -1)])

    # Phase 2: the module owning the first idempotent endpoint (e-waste
    # submission) is responsible for this index, per the convention noted
    # in app/core/idempotency.py.
    #
    # Phase 11 security fix: the cache is now scoped per user
    # (user_id, idempotency_key, scope), not just (idempotency_key,
    # scope) — see app/core/idempotency.py for why. MongoDB does not
    # replace an index when its key spec changes, so the original
    # 2-field unique index is dropped first (if present) rather than
    # left in place silently enforcing the old, wrong cross-user
    # uniqueness constraint. PARTIAL, not plain, unique index on the
    # new spec — real historical documents from Phases 2-10 predate the
    # user_id field entirely, and a plain unique index would treat all
    # of those as colliding duplicate nulls on startup against the real
    # database, exactly the failure mode already hit and fixed
    # repeatedly in this file (wards.rrr_centre_id, ai_classifications.
    # classification_id, payments.lot_id). Old cached entries simply
    # become unreachable by the new user-scoped lookup — harmless, since
    # idempotency keys are only ever meant to be replayed within the
    # same short-lived client retry attempt, never long afterward.
    try:
        await db.idempotency_keys.drop_index([("idempotency_key", 1), ("scope", 1)])
    except Exception:
        pass  # didn't exist yet (fresh database) — nothing to drop
    await db.idempotency_keys.create_index(
        [("user_id", 1), ("idempotency_key", 1), ("scope", 1)],
        unique=True,
        partialFilterExpression={"user_id": {"$exists": True}},
        name="user_idempotency_key_scope_unique",
    )

    await db.wards.create_index("ward_id", unique=True)

    await db.home_users.create_index("user_id", unique=True)
    await db.notifications.create_index("notification_id", unique=True)
    await db.notifications.create_index(
        [("user_id", 1), ("event_key", 1)],
        unique=True,
        name="user_notification_event_unique",
    )
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("read", 1)])

    # Same stale-index problem as recyclers.recycler_code/recycler_id below:
    # this database's `collectors` collection carries a plain unique index
    # on `phone`, a field app/modules/collectors/service.py has never
    # written — found live when it blocked every collector creation after
    # the first with a misleading INTERNAL_ERROR (real cause: DuplicateKeyError
    # on `phone: null`, not employee_id).
    try:
        await db.collectors.drop_index("phone_1")
    except Exception:
        pass  # already absent (fresh database, or already cleaned up)
    await db.collectors.create_index("user_id", unique=True)
    await db.collectors.create_index("employee_id", unique=True)

    await db.e_waste_submissions.create_index("submission_id", unique=True)
    await db.e_waste_submissions.create_index([("home_user_id", 1), ("status", 1)])
    # Phase 4: supports the collector pending-queue query (own ward,
    # status=WAITING_FOR_COLLECTION) — additive, doesn't change any
    # existing document shape or the index above.
    await db.e_waste_submissions.create_index([("ward_id", 1), ("status", 1)])
    await db.e_waste_submissions.create_index([("assigned_collector_id", 1), ("status", 1)])

    await db.collection_handovers.create_index("submission_id", unique=True)

    # Phase 5: RRR centres, manual classification, lots.
    await db.rrr_centres.create_index("user_id", unique=True)
    await db.rrr_centres.create_index("rrr_id", unique=True)
    await db.rrr_centres.create_index("tender_id", unique=True)

    # Partial (not plain) unique index: most wards have no rrr_centre_id
    # yet, and a plain unique index would treat every one of those missing
    # values as a colliding duplicate "null" the moment a second ward is
    # created — exactly the real failure mode hit with unrelated legacy
    # data in Phase 3. Restricting the index to documents that actually
    # have the field enforces "one RRR per ward" without that collision.
    await db.wards.create_index(
        "rrr_centre_id", unique=True, partialFilterExpression={"rrr_centre_id": {"$exists": True}}
    )

    await db.ai_classifications.create_index("item_id")

    await db.lots.create_index("lot_id", unique=True)
    await db.lots.create_index([("rrr_id", 1), ("status", 1)])

    # Phase 6: recyclers, bids.
    #
    # This database's `recyclers` collection carries stale plain-unique
    # indexes on `recycler_code` and `recycler_id` — fields this module has
    # never written (it only ever sets user_id/license_id/company_name/
    # status/created_at). A plain unique index treats every document
    # missing the field as a colliding "null", so the moment one legacy
    # document occupied that null slot, EVERY subsequent recycler
    # registration failed at insert — misreported as
    # LICENSE_ID_ALREADY_EXISTS even for a genuinely new license ID,
    # because the real DuplicateKeyError was on recycler_code/recycler_id,
    # not license_id. Same drop-then-recreate pattern as idempotency_keys
    # above.
    for stale_index in ("recycler_code_1", "recycler_id_1"):
        try:
            await db.recyclers.drop_index(stale_index)
        except Exception:
            pass  # already absent (fresh database, or already cleaned up)
    await db.recyclers.create_index("user_id", unique=True)
    await db.recyclers.create_index("license_id", unique=True)

    await db.bids.create_index("bid_id", unique=True)
    await db.bids.create_index([("lot_id", 1), ("status", 1)])
    await db.bids.create_index([("recycler_id", 1), ("status", 1)])
    # The actual race-safe guarantee behind "only one accepted bid per
    # lot" (architecture Section 3, corrected design): keyed on lot_id
    # ALONE, never (lot_id, recycler_id) — including recycler_id in the
    # key would let two different recyclers each hold their own "one
    # accepted bid per lot per recycler" slot, which defeats the point.
    # Partial (status=ACCEPTED only) for the same reason every other
    # partial index in this file exists: most bids are never ACCEPTED,
    # and a plain unique index would treat all of those as colliding nulls.
    await db.bids.create_index(
        "lot_id", unique=True, partialFilterExpression={"status": "ACCEPTED"}, name="lot_id_accepted_unique"
    )

    # Phase 7: complaints (architecture Section 13).
    await db.complaints.create_index("complaint_id", unique=True)
    await db.complaints.create_index([("reporter_id", 1), ("status", 1)])
    await db.complaints.create_index("status")

    # Phase 8: AI classification. ai_classifications.item_id index already
    # existed since Phase 5; classification_id is new and additive.
    # PARTIAL, not plain, unique index — real historical documents from
    # Phase 5/6 live verification predate this field and don't have it at
    # all, so a plain unique index would treat every one of those missing
    # values as a colliding duplicate "null" on first startup against the
    # real database, exactly the failure mode already hit for real with
    # wards.rrr_centre_id (Phase 5) and unrelated legacy collectors data
    # (Phase 3). Restricting to documents that actually have the field
    # avoids that collision while still guaranteeing uniqueness for every
    # classification written from this phase onward.
    await db.ai_classifications.create_index(
        "classification_id", unique=True, partialFilterExpression={"classification_id": {"$exists": True}}
    )

    # Phase 9: logistics, payments, rewards.
    await db.logistics_bookings.create_index("booking_id", unique=True)
    # One active booking per lot (architecture Section 3) — plain unique is
    # safe here since every booking document always has lot_id from the
    # moment it's created (unlike the partial-index cases above, there's
    # no pre-existing collection of documents missing this field).
    await db.logistics_bookings.create_index("lot_id", unique=True)

    await db.payments.create_index("payment_id", unique=True)
    await db.payments.create_index([("lot_id", 1), ("status", 1)])
    # The actual duplicate-payment guarantee (architecture Section 3/11):
    # at most one SUCCEEDED payment per lot, enforced at the database
    # level — same partial-unique-index shape as bids.lot_id's
    # accepted-only index, for the identical reason (most payment
    # attempts are never SUCCEEDED; a plain unique index would treat all
    # of those as colliding nulls).
    await db.payments.create_index(
        "lot_id", unique=True, partialFilterExpression={"status": "SUCCEEDED"}, name="lot_id_succeeded_unique"
    )
    # Architecture Section 3 lists idempotency_key directly on the payment
    # document with its own unique index — a new collection with no
    # pre-existing documents, so a plain (not partial) unique index is
    # safe; every payment document always has this field set.
    await db.payments.create_index("idempotency_key", unique=True)

    await db.rewards.create_index("reward_id", unique=True)
    # Prevents double reward computation for the same home user/period —
    # the structural guarantee behind "one reward per user per period",
    # not just an application-level check.
    await db.rewards.create_index([("home_user_id", 1), ("period", 1)], unique=True)

    await db.reward_transactions.create_index("txn_id", unique=True)
    await db.reward_transactions.create_index([("home_user_id", 1), ("type", 1)])


def set_db_for_testing(db: AsyncIOMotorDatabase) -> None:
    """Test-only hook: point the module-level _db at an in-memory mongomock
    database instead of a real MongoDB connection."""
    global _db
    _db = db
