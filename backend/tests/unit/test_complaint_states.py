"""
Pure stdlib-only tests for app.state_machines.complaint_states — no
FastAPI/Mongo dependency, same pattern as the other three state machines.
"""
import pytest

from app.state_machines.complaint_states import InvalidComplaintStateTransitionError, transition


def test_open_can_move_to_in_progress():
    assert transition("OPEN", "IN_PROGRESS") == "IN_PROGRESS"


def test_in_progress_can_be_resolved():
    assert transition("IN_PROGRESS", "RESOLVED") == "RESOLVED"


def test_in_progress_can_be_rejected():
    assert transition("IN_PROGRESS", "REJECTED") == "REJECTED"


def test_in_progress_can_be_escalated():
    assert transition("IN_PROGRESS", "ESCALATED") == "ESCALATED"


def test_open_cannot_be_resolved_directly():
    with pytest.raises(InvalidComplaintStateTransitionError):
        transition("OPEN", "RESOLVED")


def test_resolved_is_terminal():
    with pytest.raises(InvalidComplaintStateTransitionError):
        transition("RESOLVED", "IN_PROGRESS")


def test_rejected_is_terminal():
    with pytest.raises(InvalidComplaintStateTransitionError):
        transition("REJECTED", "IN_PROGRESS")


def test_escalated_is_terminal():
    with pytest.raises(InvalidComplaintStateTransitionError):
        transition("ESCALATED", "RESOLVED")


def test_unknown_state_names_are_rejected():
    with pytest.raises(InvalidComplaintStateTransitionError):
        transition("NOT_A_REAL_STATE", "OPEN")


def test_error_carries_from_and_to_state():
    with pytest.raises(InvalidComplaintStateTransitionError) as exc_info:
        transition("RESOLVED", "OPEN")
    assert exc_info.value.from_state == "RESOLVED"
    assert exc_info.value.to_state == "OPEN"
