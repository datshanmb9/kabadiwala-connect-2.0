import '../../core/api_client.dart';
import '../../core/api_exception.dart';
import '../../core/auth_storage.dart';
import 'models/auth_session.dart';

/// This app serves two roles sharing one codebase, per the architecture's
/// "one Flutter codebase, strictly role-isolated" decision: HOME_USER and
/// COLLECTOR. Any other role (GOVERNMENT_ADMIN, RECYCLER, RRR_CENTER) is
/// refused here — even though the backend RBAC would reject any actual
/// API call from the wrong role anyway, we refuse to even hold onto an
/// out-of-scope session client-side rather than silently proceeding into
/// a broken UI. AuthGate is what actually picks the separate nav graph
/// per role once login succeeds.
const _supportedRoles = {'HOME_USER', 'COLLECTOR'};

class WrongRoleException implements Exception {
  final String role;
  const WrongRoleException(this.role);
}

class AuthRepository {
  final ApiClient apiClient;
  final AuthStorage authStorage;

  AuthRepository({required this.apiClient, required this.authStorage});

  Future<AuthSession> login(String username, String password) async {
    final tokenJson = await apiClient.post(
      '/api/v1/auth/login',
      body: {'username': username, 'password': password},
    );
    final accessToken = tokenJson['access_token'] as String;
    final refreshToken = tokenJson['refresh_token'] as String;
    final role = tokenJson['role'] as String;

    if (!_supportedRoles.contains(role)) {
      throw WrongRoleException(role);
    }

    final me = await apiClient.get('/api/v1/auth/me', token: accessToken);
    final session = AuthSession(
      accessToken: accessToken,
      refreshToken: refreshToken,
      role: role,
      userId: me['user_id'] as String,
      username: me['username'] as String,
    );
    await authStorage.saveSession(session);
    return session;
  }

  /// Called once at app startup. Returns null (and clears any stale
  /// storage) if there's no session, the token is dead and refresh also
  /// fails, or the account is no longer a HOME_USER (e.g. status changed
  /// server-side) — every one of those cases means "show the login screen"
  /// rather than crash.
  Future<AuthSession?> restoreSession() async {
    final stored = await authStorage.loadSession();
    if (stored == null) return null;

    try {
      final me = await apiClient.get('/api/v1/auth/me', token: stored.accessToken);
      if (!_supportedRoles.contains(me['role'])) {
        await authStorage.clear();
        return null;
      }
      final refreshed = stored.copyWith(
        userId: me['user_id'] as String,
        username: me['username'] as String,
      );
      await authStorage.saveSession(refreshed);
      return refreshed;
    } on ApiException catch (e) {
      if (!e.isInvalidToken) {
        await authStorage.clear();
        return null;
      }
    }

    // Access token expired/invalid — try the refresh token once.
    try {
      final refreshJson = await apiClient.post(
        '/api/v1/auth/refresh',
        body: {'refresh_token': stored.refreshToken},
      );
      final newAccessToken = refreshJson['access_token'] as String;
      final me = await apiClient.get('/api/v1/auth/me', token: newAccessToken);
      if (!_supportedRoles.contains(me['role'])) {
        await authStorage.clear();
        return null;
      }
      final refreshed = stored.copyWith(
        accessToken: newAccessToken,
        userId: me['user_id'] as String,
        username: me['username'] as String,
      );
      await authStorage.saveSession(refreshed);
      return refreshed;
    } catch (_) {
      await authStorage.clear();
      return null;
    }
  }

  /// Exchanges the refresh token for a new access token mid-session (used
  /// by background offline-submission sync, which can run long after the
  /// short-lived access token expired). Returns null if refresh fails.
  Future<AuthSession?> refreshAccessToken(AuthSession session) async {
    try {
      final refreshJson = await apiClient.post(
        '/api/v1/auth/refresh',
        body: {'refresh_token': session.refreshToken},
      );
      final refreshed = session.copyWith(accessToken: refreshJson['access_token'] as String);
      await authStorage.saveSession(refreshed);
      return refreshed;
    } on ApiException {
      return null;
    }
  }

  Future<void> logout(AuthSession session) async {
    try {
      await apiClient.post('/api/v1/auth/logout', token: session.accessToken);
    } catch (_) {
      // Best-effort server-side invalidation; local session is cleared
      // regardless so the user is never stuck "logged in" on this device.
    }
    await authStorage.clear();
  }
}
