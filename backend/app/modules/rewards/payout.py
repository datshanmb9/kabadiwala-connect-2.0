"""
Mock UPI payout (architecture Section 12) — Government -> UPI is the
intended real direction, but Phase 9 ships a MOCK payout only, same
"deterministic, offline, no real credential" design as
payments/gateway.py. Never accepts or stores a UPI PIN or any banking
password — the redemption flow only ever reads the home user's own
`upi_id` (an account identifier, not a credential) already on file from
registration.
"""
import hashlib
from dataclasses import dataclass

MOCK_PAYOUT_SUCCESS_RATE = 0.9  # arbitrary, for demo variety only


@dataclass(frozen=True)
class PayoutResult:
    succeeded: bool
    reference: str


def payout(reward_id: str, amount_str: str) -> PayoutResult:
    digest = hashlib.sha256(f"mock-payout:{reward_id}:{amount_str}".encode("utf-8")).hexdigest()
    score = int(digest[:8], 16) / 0xFFFFFFFF
    succeeded = score < MOCK_PAYOUT_SUCCESS_RATE
    return PayoutResult(succeeded=succeeded, reference=f"MOCK-UPI-{digest[:16]}")
