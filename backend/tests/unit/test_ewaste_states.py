"""
Pure stdlib-only tests for app.state_machines.ewaste_states — no
FastAPI/Mongo dependency.
"""
import pytest

from app.state_machines.ewaste_states import InvalidStateTransitionError, transition

FULL_HAPPY_PATH = [
    "CREATED",
    "PHOTO_CAPTURED",
    "WAITING_FOR_COLLECTION",
    "COLLECTOR_ASSIGNED",
    "HANDOVER_PENDING",
    "LOCATION_VERIFIED",
    "COLLECTED",
    "AT_RRR",
    "CLASSIFIED",
    "LOT_CREATED",
    "LISTED_FOR_BIDDING",
    "BID_SELECTED",
    "LOGISTICS_BOOKED",
    "READY_FOR_COLLECTION",
    "PAYMENT_PENDING",
    "PAID",
    "COMPLETED",
]


def test_full_happy_path_chain_is_all_valid():
    state = FULL_HAPPY_PATH[0]
    for next_state in FULL_HAPPY_PATH[1:]:
        state = transition(state, next_state)
    assert state == "COMPLETED"


def test_collector_acceptance_path_is_valid():
    state = transition("WAITING_FOR_COLLECTION", "COLLECTOR_ASSIGNED")
    state = transition(state, "COLLECTOR_ACCEPTED")
    state = transition(state, "COLLECTING")
    state = transition(state, "HANDOVER_PENDING")
    assert state == "HANDOVER_PENDING"


def test_flagged_for_review_branch_from_handover_pending():
    assert transition("HANDOVER_PENDING", "FLAGGED_FOR_REVIEW") == "FLAGGED_FOR_REVIEW"


def test_flagged_for_review_can_retry_to_handover_pending():
    assert transition("FLAGGED_FOR_REVIEW", "HANDOVER_PENDING") == "HANDOVER_PENDING"


def test_flagged_for_review_can_go_terminal_rejected():
    assert transition("FLAGGED_FOR_REVIEW", "REJECTED") == "REJECTED"


def test_bid_selected_can_reopen_to_listed_for_bidding():
    """Phase 6 addition: an RRR cancelling a bid acceptance within 24h
    reopens the lot for bidding; items must be able to follow."""
    assert transition("BID_SELECTED", "LISTED_FOR_BIDDING") == "LISTED_FOR_BIDDING"


def test_at_rrr_can_branch_to_needs_review():
    """Phase 8 addition: a low-confidence/failed AI classification
    attempt routes here instead of silently proceeding to CLASSIFIED."""
    assert transition("AT_RRR", "NEEDS_REVIEW") == "NEEDS_REVIEW"


def test_needs_review_can_be_manually_resolved_to_classified():
    assert transition("NEEDS_REVIEW", "CLASSIFIED") == "CLASSIFIED"


def test_needs_review_cannot_skip_back_to_at_rrr():
    with pytest.raises(InvalidStateTransitionError):
        transition("NEEDS_REVIEW", "AT_RRR")


def test_classified_cannot_go_back_to_needs_review():
    with pytest.raises(InvalidStateTransitionError):
        transition("CLASSIFIED", "NEEDS_REVIEW")


def test_payment_pending_can_revert_to_ready_for_collection_on_failure():
    """Phase 9 addition: mirrors the same reopen edge added to
    lot_states.py — a failed mock payment attempt reverts the item
    alongside its lot."""
    assert transition("PAYMENT_PENDING", "READY_FOR_COLLECTION") == "READY_FOR_COLLECTION"


def test_paid_cannot_revert_to_payment_pending():
    with pytest.raises(InvalidStateTransitionError):
        transition("PAID", "PAYMENT_PENDING")


def test_arbitrary_skip_is_rejected():
    with pytest.raises(InvalidStateTransitionError):
        transition("CREATED", "COLLECTED")


def test_backward_transition_is_rejected():
    with pytest.raises(InvalidStateTransitionError):
        transition("COLLECTED", "HANDOVER_PENDING")


def test_transition_from_terminal_completed_is_rejected():
    with pytest.raises(InvalidStateTransitionError):
        transition("COMPLETED", "PAID")


def test_transition_from_terminal_rejected_is_rejected():
    with pytest.raises(InvalidStateTransitionError):
        transition("REJECTED", "HANDOVER_PENDING")


def test_unknown_state_names_are_rejected():
    with pytest.raises(InvalidStateTransitionError):
        transition("NOT_A_REAL_STATE", "COLLECTED")


def test_error_carries_from_and_to_state():
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        transition("CREATED", "COLLECTED")
    assert exc_info.value.from_state == "CREATED"
    assert exc_info.value.to_state == "COLLECTED"
