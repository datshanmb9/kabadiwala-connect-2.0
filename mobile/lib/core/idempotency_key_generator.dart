import 'package:uuid/uuid.dart';

/// Client-generated idempotency keys for state-changing requests (Section
/// on offline/retry safety in the architecture doc: "Client-generated
/// idempotency key persisted with the local draft, sent unchanged on
/// retry"). A screen generates ONE key when a submission attempt begins
/// and reuses it for every retry of that same attempt — a fresh key is
/// only generated for a genuinely new attempt (e.g. a new photo/location).
class IdempotencyKeyGenerator {
  static const Uuid _uuid = Uuid();

  static String generate() => _uuid.v4();
}
