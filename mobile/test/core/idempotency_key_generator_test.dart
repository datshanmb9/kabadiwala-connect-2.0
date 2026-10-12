import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/core/idempotency_key_generator.dart';

void main() {
  test('generates a valid UUID v4 formatted string', () {
    final key = IdempotencyKeyGenerator.generate();
    final uuidV4Pattern = RegExp(
      r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
      caseSensitive: false,
    );
    expect(uuidV4Pattern.hasMatch(key), isTrue, reason: 'got: $key');
  });

  test('generates a distinct key on every call', () {
    final keys = List.generate(50, (_) => IdempotencyKeyGenerator.generate());
    expect(keys.toSet().length, 50);
  });
}
