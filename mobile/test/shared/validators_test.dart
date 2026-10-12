import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/shared/validators.dart';

void main() {
  group('Validators.required', () {
    test('rejects null and empty/whitespace', () {
      expect(Validators.required(null), isNotNull);
      expect(Validators.required(''), isNotNull);
      expect(Validators.required('   '), isNotNull);
    });

    test('accepts non-empty text', () {
      expect(Validators.required('hello'), isNull);
    });
  });

  group('Validators.username', () {
    test('rejects short usernames', () {
      expect(Validators.username('ab'), isNotNull);
    });

    test('accepts a valid username', () {
      expect(Validators.username('citizen1'), isNull);
    });
  });

  group('Validators.password', () {
    test('rejects short passwords', () {
      expect(Validators.password('abc12'), isNotNull);
    });

    test('accepts a valid password', () {
      expect(Validators.password('longenough123'), isNull);
    });
  });

  group('Validators.latitude / longitude', () {
    test('rejects null coordinates', () {
      expect(Validators.latitude(null), isNotNull);
      expect(Validators.longitude(null), isNotNull);
    });

    test('rejects out-of-range coordinates', () {
      expect(Validators.latitude(91.0), isNotNull);
      expect(Validators.longitude(-181.0), isNotNull);
    });

    test('accepts valid coordinates', () {
      expect(Validators.latitude(12.9716), isNull);
      expect(Validators.longitude(77.5946), isNull);
    });
  });
}
