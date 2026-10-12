/**
 * Client-generated idempotency keys for state-changing requests, same
 * pattern as rrr-centre-web and the Flutter app: a screen generates ONE
 * key when an attempt begins and reuses it for retries of that same
 * attempt. `crypto.randomUUID()` is a native browser API, no dependency.
 */
export function generateIdempotencyKey(): string {
  return crypto.randomUUID()
}
