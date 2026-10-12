import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/core/config.dart';

void main() {
  test(
    'apiBaseUrl never defaults to the literal "localhost" — Phase 10 regression guard for the '
    'IPv4/IPv6 dual-stack loopback bug found in rrr-centre-web (Phase 5) and propagated here',
    () {
      // On this test's platform (desktop/VM test runner, not web, not
      // Android), apiBaseUrl falls through to the shared non-web,
      // non-Android default — which must be 127.0.0.1, not localhost.
      expect(AppConfig.apiBaseUrl, isNot(contains('localhost')));
      expect(AppConfig.apiBaseUrl, contains('127.0.0.1'));
    },
  );
}
