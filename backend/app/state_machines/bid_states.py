"""
Explicit, allow-listed BID (not lot, not item) state transitions (Section
6.2 of the architecture doc) — a third, independent state machine
alongside app/state_machines/{ewaste_states,lot_states}.py. A bid's status
is driven by the bids module's service layer only.
"""

ALL_STATES = ("PLACED", "CANCELLED", "ACCEPTED", "REJECTED")

ALLOWED_TRANSITIONS = frozenset(
    {
        # Recycler-initiated, only before acceptance.
        ("PLACED", "CANCELLED"),
        # RRR-initiated, only one bid per lot (enforced at the DB level by
        # a partial unique index on bids.lot_id where status=ACCEPTED —
        # see app/db/mongo.py — not by this allow-list, which only says
        # the transition is *shaped* correctly).
        ("PLACED", "ACCEPTED"),
        # Implicit, when a sibling bid on the same lot is ACCEPTED.
        ("PLACED", "REJECTED"),
        # RRR-initiated, only within 24h and before payment (Phase 9 will
        # add the payment half of this guard once a payments module
        # exists; the 24h half is enforced now).
        ("ACCEPTED", "CANCELLED"),
    }
)


class InvalidBidStateTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid bid state transition: {from_state} -> {to_state}")


def transition(current_state: str, target_state: str) -> str:
    if (current_state, target_state) not in ALLOWED_TRANSITIONS:
        raise InvalidBidStateTransitionError(current_state, target_state)
    return target_state
