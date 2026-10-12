"""
Explicit, allow-listed COMPLAINT state transitions (architecture Section
13) — a fourth, independent state machine alongside
app/state_machines/{ewaste_states,lot_states,bid_states}.py. A complaint's
status is driven by the complaints module's service layer only.
"""

ALL_STATES = ("OPEN", "IN_PROGRESS", "RESOLVED", "REJECTED", "ESCALATED")

ALLOWED_TRANSITIONS = frozenset(
    {
        # Admin reviews a freshly-filed complaint.
        ("OPEN", "IN_PROGRESS"),
        # Admin resolves/rejects/escalates — only from IN_PROGRESS, per the
        # architecture doc's own lifecycle diagram (Section 13): "Admin
        # reviews -> IN_PROGRESS -> Admin resolves/rejects/escalates ->
        # RESOLVED / REJECTED / ESCALATED".
        ("IN_PROGRESS", "RESOLVED"),
        ("IN_PROGRESS", "REJECTED"),
        ("IN_PROGRESS", "ESCALATED"),
    }
)


class InvalidComplaintStateTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid complaint state transition: {from_state} -> {to_state}")


def transition(current_state: str, target_state: str) -> str:
    if (current_state, target_state) not in ALLOWED_TRANSITIONS:
        raise InvalidComplaintStateTransitionError(current_state, target_state)
    return target_state
