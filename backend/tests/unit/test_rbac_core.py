"""
These tests import ONLY app.core.rbac_core, which has zero external
dependencies (no FastAPI, no Mongo) — so they can run in any environment
with a bare Python interpreter, including this sandbox. Written in pytest
style (bare `assert`, `test_*` functions) so `pytest tests/unit/test_rbac_core.py`
works once pytest is installed; also runnable directly, see
scripts/run_offline_unit_tests.py.
"""
from app.core.rbac_core import is_owner, role_is_allowed


def test_no_allowed_roles_means_any_authenticated_role_passes():
    assert role_is_allowed("HOME_USER", ()) is True
    assert role_is_allowed("GOVERNMENT_ADMIN", ()) is True


def test_role_in_allow_list_passes():
    assert role_is_allowed("GOVERNMENT_ADMIN", ("GOVERNMENT_ADMIN",)) is True


def test_role_not_in_allow_list_is_rejected():
    assert role_is_allowed("RECYCLER", ("GOVERNMENT_ADMIN",)) is False


def test_role_gate_with_multiple_allowed_roles():
    assert role_is_allowed("RRR_CENTER", ("RRR_CENTER", "GOVERNMENT_ADMIN")) is True
    assert role_is_allowed("HOME_USER", ("RRR_CENTER", "GOVERNMENT_ADMIN")) is False


def test_is_owner_true_when_ids_match():
    assert is_owner("recycler-123", "recycler-123") is True


def test_is_owner_false_when_ids_differ():
    # This is the concrete check that stops "recycler A modifying recycler
    # B's bids" and "one RRR centre modifying another RRR centre's lots" —
    # role_is_allowed alone would let both requests through since both
    # callers hold the same role.
    assert is_owner("recycler-123", "recycler-456") is False


def test_role_check_alone_is_not_ownership_check():
    # Same role, different identity: role_is_allowed says yes, is_owner says
    # no. Both must be satisfied — this test documents why the service
    # layer never relies on role_is_allowed by itself for "own X only" rules.
    caller_role = "RECYCLER"
    caller_id = "recycler-123"
    resource_owner_id = "recycler-456"

    role_gate_passes = role_is_allowed(caller_role, ("RECYCLER",))
    ownership_gate_passes = is_owner(resource_owner_id, caller_id)

    assert role_gate_passes is True
    assert ownership_gate_passes is False
