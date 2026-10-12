import 'package:kabadiwala_mobile/core/auth_storage.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';

/// Test double for AuthStorage: real FlutterSecureStorage requires a
/// platform channel that isn't wired up under `flutter test`, so
/// repository/controller tests use this in-memory stand-in instead.
class InMemoryAuthStorage extends AuthStorage {
  AuthSession? _session;

  @override
  Future<void> saveSession(AuthSession session) async {
    _session = session;
  }

  @override
  Future<AuthSession?> loadSession() async => _session;

  @override
  Future<void> clear() async {
    _session = null;
  }
}
