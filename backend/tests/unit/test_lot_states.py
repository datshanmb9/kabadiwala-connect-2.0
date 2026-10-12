"""
Pure stdlib-only tests for app.state_machines.lot_states — no
FastAPI/Mongo dependency, same pattern as test_ewaste_states.py.
"""
import pytest

from app.state_machines.lot_states import InvalidLotStateTransitionError, transition

FULL_HAPPY_PATH = [
    "DRAFT",
    "LISTED_FOR_BIDDING",
    "BID_SELECTED",
    "LOGISTICS_BOOKED",
    "READY_FOR_COLLECTION",
    "PAYMENT_PENDING",
    "SOLD",
    "COMPLETED",
]


def test_full_happy_path_chain_is_all_valid():
    state = FULL_HAPPY_PATH[0]
    for next_state in FULL_HAPPY_PATH[1:]:
        state = transition(state, next_state)
    assert state == "COMPLETED"


def test_bid_selected_can_reopen_to_listed_for_bidding():
    """RRR cancels acceptance within 24h/before payment (Section 10)."""
    assert transition("BID_SELECTED", "LISTED_FOR_BIDDING") == "LISTED_FOR_BIDDING"


def test_payment_pending_can_revert_to_ready_for_collection_on_failure():
    """Phase 9 addition: a failed mock-gateway attempt must not leave the
    lot stuck in PAYMENT_PENDING (architecture Section 11)."""
    assert transition("PAYMENT_PENDING", "READY_FOR_COLLECTION") == "READY_FOR_COLLECTION"


def test_sold_cannot_revert_to_payment_pending():
    with pytest.raises(InvalidLotStateTransitionError):
        transition("SOLD", "PAYMENT_PENDING")


def test_arbitrary_skip_is_rejected():
    with pytest.raises(InvalidLotStateTransitionError):
        transition("DRAFT", "SOLD")


def test_backward_transition_past_the_allowed_reopen_is_rejected():
    with pytest.raises(InvalidLotStateTransitionError):
        transition("LOGISTICS_BOOKED", "DRAFT")


def test_transition_from_terminal_completed_is_rejected():
    with pytest.raises(InvalidLotStateTransitionError):
        transition("COMPLETED", "SOLD")


def test_unknown_state_names_are_rejected():
    with pytest.raises(InvalidLotStateTransitionError):
        transition("NOT_A_REAL_STATE", "DRAFT")


def test_error_carries_from_and_to_state():
    with pytest.raises(InvalidLotStateTransitionError) as exc_info:
        transition("DRAFT", "SOLD")
    assert exc_info.value.from_state == "DRAFT"
    assert exc_info.value.to_state == "SOLD"
