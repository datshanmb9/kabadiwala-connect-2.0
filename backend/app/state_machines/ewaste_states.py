"""
Explicit, allow-listed e-waste item state transitions (Section 6.1 of the
architecture doc). Pure, dependency-free (no FastAPI, no Mongo) — same
pattern as app/core/rbac_core.py — so the transition table itself can be
unit-tested with nothing but the standard library.

No endpoint writes a `status` field directly; every write goes through
`transition()`, and any (from, to) pair not in ALLOWED_TRANSITIONS raises
InvalidStateTransitionError, which the service layer turns into the
structured INVALID_STATE_TRANSITION error response.
"""

ALL_STATES = (
    "CREATED",
    "PHOTO_CAPTURED",
    "WAITING_FOR_COLLECTION",
    "COLLECTOR_ASSIGNED",
    "COLLECTOR_ACCEPTED",
    "COLLECTING",
    "HANDOVER_PENDING",
    "LOCATION_VERIFIED",
    "COLLECTED",
    "AT_RRR",
    "CLASSIFIED",
    # Phase 8: AI classification attempted but the result was low-confidence
    # or the classifier itself failed — routes here instead of silently
    # accepting an unreliable category, mirroring the same
    # "verification failure never silently proceeds" principle as
    # HANDOVER_PENDING -> FLAGGED_FOR_REVIEW.
    "NEEDS_REVIEW",
    "LOT_CREATED",
    "LISTED_FOR_BIDDING",
    "BID_SELECTED",
    "LOGISTICS_BOOKED",
    "READY_FOR_COLLECTION",
    "PAYMENT_PENDING",
    "PAID",
    "COMPLETED",
    "FLAGGED_FOR_REVIEW",
    "REJECTED",
)

ALLOWED_TRANSITIONS = frozenset(
    {
        ("CREATED", "PHOTO_CAPTURED"),
        ("PHOTO_CAPTURED", "WAITING_FOR_COLLECTION"),
        ("WAITING_FOR_COLLECTION", "COLLECTOR_ASSIGNED"),
        ("COLLECTOR_ASSIGNED", "COLLECTOR_ACCEPTED"),
        ("COLLECTOR_ACCEPTED", "COLLECTING"),
        ("COLLECTING", "HANDOVER_PENDING"),
        ("COLLECTOR_ASSIGNED", "HANDOVER_PENDING"),
        ("HANDOVER_PENDING", "LOCATION_VERIFIED"),
        # Side branch (Section 6.1): geo/timestamp verification failure
        # routes here instead of silently proceeding to LOCATION_VERIFIED.
        ("HANDOVER_PENDING", "FLAGGED_FOR_REVIEW"),
        # Admin-triggered recovery from a flagged handover.
        ("FLAGGED_FOR_REVIEW", "HANDOVER_PENDING"),
        ("FLAGGED_FOR_REVIEW", "REJECTED"),
        ("LOCATION_VERIFIED", "COLLECTED"),
        ("COLLECTED", "AT_RRR"),
        ("AT_RRR", "CLASSIFIED"),
        # Phase 8: AI classification side branch (Section 9) — same shape
        # as the Phase 2 handover side branch. Low confidence or a
        # classifier failure routes here instead of AT_RRR -> CLASSIFIED.
        ("AT_RRR", "NEEDS_REVIEW"),
        # RRR staff resolves it with a manual category via the SAME
        # classify() function Phase 5 already uses for AT_RRR -> CLASSIFIED
        # — this is the only way out of NEEDS_REVIEW, so it always ends in
        # a genuine human-confirmed category.
        ("NEEDS_REVIEW", "CLASSIFIED"),
        ("CLASSIFIED", "LOT_CREATED"),
        ("LOT_CREATED", "LISTED_FOR_BIDDING"),
        ("LISTED_FOR_BIDDING", "BID_SELECTED"),
        # Phase 6 addition: an RRR cancelling a bid acceptance within 24h
        # reopens the lot (BID_SELECTED -> LISTED_FOR_BIDDING at the lot
        # level, already defined in lot_states.py since Phase 5) — items
        # in that lot need the same reverse transition to stay in sync.
        ("BID_SELECTED", "LISTED_FOR_BIDDING"),
        ("BID_SELECTED", "LOGISTICS_BOOKED"),
        ("LOGISTICS_BOOKED", "READY_FOR_COLLECTION"),
        ("READY_FOR_COLLECTION", "PAYMENT_PENDING"),
        # Phase 9 addition: mirrors the same reopen edge added to
        # lot_states.py — a failed mock payment attempt reverts the item
        # alongside its lot, never leaving either stuck mid-payment.
        ("PAYMENT_PENDING", "READY_FOR_COLLECTION"),
        ("PAYMENT_PENDING", "PAID"),
        ("PAID", "COMPLETED"),
    }
)


class InvalidStateTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid state transition: {from_state} -> {to_state}")


def transition(current_state: str, target_state: str) -> str:
    """Returns target_state if the transition is allowed, otherwise raises
    InvalidStateTransitionError. Never mutates anything itself — callers are
    responsible for persisting the returned value."""
    if (current_state, target_state) not in ALLOWED_TRANSITIONS:
        raise InvalidStateTransitionError(current_state, target_state)
    return target_state
