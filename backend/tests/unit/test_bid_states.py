"""
Pure stdlib-only tests for app.state_machines.bid_states — no
FastAPI/Mongo dependency, same pattern as the other two state machines.
"""
import pytest

from app.state_machines.bid_states import InvalidBidStateTransitionError, transition


def test_placed_can_be_cancelled():
    assert transition("PLACED", "CANCELLED") == "CANCELLED"


def test_placed_can_be_accepted():
    assert transition("PLACED", "ACCEPTED") == "ACCEPTED"


def test_placed_can_be_implicitly_rejected():
    assert transition("PLACED", "REJECTED") == "REJECTED"


def test_accepted_can_be_cancelled_within_window():
    assert transition("ACCEPTED", "CANCELLED") == "CANCELLED"


def test_cancelled_is_terminal():
    with pytest.raises(InvalidBidStateTransitionError):
        transition("CANCELLED", "PLACED")


def test_rejected_is_terminal():
    with pytest.raises(InvalidBidStateTransitionError):
        transition("REJECTED", "ACCEPTED")


def test_accepted_cannot_go_back_to_placed():
    with pytest.raises(InvalidBidStateTransitionError):
        transition("ACCEPTED", "PLACED")


def test_unknown_state_names_are_rejected():
    with pytest.raises(InvalidBidStateTransitionError):
        transition("NOT_A_REAL_STATE", "PLACED")


def test_error_carries_from_and_to_state():
    with pytest.raises(InvalidBidStateTransitionError) as exc_info:
        transition("CANCELLED", "ACCEPTED")
    assert exc_info.value.from_state == "CANCELLED"
    assert exc_info.value.to_state == "ACCEPTED"
