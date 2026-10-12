"""
Mock payment gateway (architecture Section 11) — MOCK_PAYMENT_GATEWAY
only, labeled as such on every payment record and API response, never
presented as a real integration. No real network call, no provider
credential of any kind — there is nothing to leak because nothing is
ever sent anywhere.

Deterministic by design, same spirit as Phase 8's
DeterministicMockClassifier: a pure hash-based function of the payment's
own amount string, so behavior is reproducible for tests and demos
rather than a coin-flip nobody can pin down. This proves integration
correctness (does the SUCCEEDED/FAILED wiring behave correctly?), never
anything about a real gateway's true approval rate.
"""
import hashlib
from dataclasses import dataclass

MOCK_SUCCESS_RATE = 0.9  # arbitrary, for demo variety only — not a claim about any real gateway


@dataclass(frozen=True)
class GatewayResult:
    succeeded: bool
    reference: str


def charge(amount_str: str) -> GatewayResult:
    digest = hashlib.sha256(f"mock-charge:{amount_str}".encode("utf-8")).hexdigest()
    score = int(digest[:8], 16) / 0xFFFFFFFF
    succeeded = score < MOCK_SUCCESS_RATE
    return GatewayResult(succeeded=succeeded, reference=f"MOCK-{digest[:16]}")
