"""
Pure tests for app.modules.rewards.payout — the mock UPI payout, same
"deterministic, offline, no real credential" design as
test_payment_gateway.py.
"""
from app.modules.rewards.payout import payout


def test_same_inputs_always_produce_the_same_result():
    assert payout("reward-1", "5.00") == payout("reward-1", "5.00")


def test_different_reward_ids_can_produce_different_results():
    results = {payout(f"reward-{i}", "5.00").succeeded for i in range(30)}
    assert len(results) > 1


def test_reference_never_contains_a_upi_pin_or_password_like_field():
    result = payout("reward-1", "5.00")
    assert "pin" not in result.reference.lower()
    assert "password" not in result.reference.lower()
