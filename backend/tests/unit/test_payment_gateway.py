"""
Pure tests for app.modules.payments.gateway — no FastAPI/Mongo
dependency.

IMPORTANT: MOCK_PAYMENT_GATEWAY is a hash-based, offline, deterministic
function, not a real payment processor. These tests validate the
SUCCEEDED/FAILED wiring is reproducible and consistent, never that it
reflects any real gateway's true approval behavior.
"""
from app.modules.payments.gateway import charge


def test_same_amount_always_produces_the_same_result():
    assert charge("500.00") == charge("500.00")


def test_different_amounts_can_produce_different_results():
    results = {charge(f"{100 + i}.00").succeeded for i in range(30)}
    assert len(results) > 1  # not a constant stub


def test_known_amount_succeeds_deterministically():
    # Derived once directly from the pure function; stable forever since
    # it has no external state. Used by integration tests as the
    # reliable "this payment succeeds" fixture value.
    result = charge("500.00")
    assert result.succeeded is True
    assert result.reference.startswith("MOCK-")


def test_known_amount_fails_deterministically():
    # Derived the same way — the reliable "this payment fails" fixture
    # value used by integration tests for the failure path.
    result = charge("100.00")
    assert result.succeeded is False
    assert result.reference.startswith("MOCK-")


def test_reference_never_contains_the_word_secret_or_key():
    result = charge("500.00")
    assert "secret" not in result.reference.lower()
    assert "key" not in result.reference.lower()
