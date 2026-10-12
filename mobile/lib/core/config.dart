import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;

/// Backend base URL. Overridable at build/run time with
/// `--dart-define=API_BASE_URL=http://your-host:8000` — never hardcode a
/// real deployment URL as the only option.
///
/// Defaults are chosen per platform because "localhost" means different
/// things depending on where the app is actually running:
/// - Web (Chrome/Edge): the browser runs on this same machine as the
///   backend, so the loopback address reaches it directly. Uses the
///   literal `127.0.0.1`, not `localhost` — a dual-stack machine can
///   resolve `localhost` to the IPv6 loopback while the backend
///   (`--host 0.0.0.0`) only listens on IPv4, which surfaces to the
///   browser as an indistinguishable "could not reach the server"
///   network error. This is the exact bug found and fixed in
///   `rrr-centre-web` during Phase 5 (see PROJECT_STATUS.md) — Phase 10
///   found it had never been propagated here, even though the Flutter
///   web build has the identical exposure.
/// - Android emulator: the emulator is its own virtual machine; `10.0.2.2`
///   is the documented special alias Android emulators use to reach the
///   host machine's loopback.
/// - A physical Android device would need the host machine's real LAN IP
///   instead — not knowable at compile time, hence the dart-define escape
///   hatch above for that case.
class AppConfig {
  static const String _override = String.fromEnvironment('API_BASE_URL');

  static String get apiBaseUrl {
    if (_override.isNotEmpty) return _override;
    if (kIsWeb) return 'http://127.0.0.1:8000';
    if (Platform.isAndroid) return 'http://127.0.0.1:8000';
    return 'http://127.0.0.1:8000';
  }

  /// How long a single HTTP call may take before we surface a
  /// NETWORK_ERROR instead of hanging the UI forever.
  static const Duration requestTimeout = Duration(seconds: 15);
}
