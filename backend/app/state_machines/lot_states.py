"""
Explicit, allow-listed LOT (not item) state transitions (Section 6.3 of
the architecture doc) — a separate state machine from
app/state_machines/ewaste_states.py, which tracks each e-waste item's own
lifecycle. A lot's status and its contained items' statuses are driven in
parallel by the lots module's service layer; neither machine reaches into
the other's collection.

Phase 5 scope: only DRAFT -> LISTED_FOR_BIDDING is actually reachable
(lot creation sets DRAFT directly, publish drives this one transition).
The rest of the table is defined now, per the architecture's full lot
lifecycle, so later phases (bidding, logistics, payments) extend an
already-correct allow-list instead of writing a new one.
"""

ALL_STATES = (
    "DRAFT",
    "LISTED_FOR_BIDDING",
    "BID_SELECTED",
    "LOGISTICS_BOOKED",
    "READY_FOR_COLLECTION",
    "PAYMENT_PENDING",
    "SOLD",
    "COMPLETED",
)

ALLOWED_TRANSITIONS = frozenset(
    {
        ("DRAFT", "LISTED_FOR_BIDDING"),
        ("LISTED_FOR_BIDDING", "BID_SELECTED"),
        # RRR cancels acceptance within 24h and before payment (Section 10).
        ("BID_SELECTED", "LISTED_FOR_BIDDING"),
        ("BID_SELECTED", "LOGISTICS_BOOKED"),
        ("LOGISTICS_BOOKED", "READY_FOR_COLLECTION"),
        ("READY_FOR_COLLECTION", "PAYMENT_PENDING"),
        # Phase 9 addition: a failed mock-gateway attempt must not leave the
        # lot stuck in PAYMENT_PENDING — Section 11: "on FAILED: lot remains
        # READY_FOR_COLLECTION, recycler may retry (same idempotency key
        # returns same result, doesn't double-charge)".
        ("PAYMENT_PENDING", "READY_FOR_COLLECTION"),
        ("PAYMENT_PENDING", "SOLD"),
        ("SOLD", "COMPLETED"),
    }
)


class InvalidLotStateTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid lot state transition: {from_state} -> {to_state}")


def transition(current_state: str, target_state: str) -> str:
    if (current_state, target_state) not in ALLOWED_TRANSITIONS:
        raise InvalidLotStateTransitionError(current_state, target_state)
    return target_state
