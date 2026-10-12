import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';

void main() {
  const session = AuthSession(
    accessToken: 'access-123',
    refreshToken: 'refresh-456',
    role: 'HOME_USER',
    userId: 'user-1',
    username: 'citizen1',
  );

  test('toJson/fromJson round-trips exactly', () {
    final restored = AuthSession.fromJson(session.toJson());
    expect(restored.accessToken, session.accessToken);
    expect(restored.refreshToken, session.refreshToken);
    expect(restored.role, session.role);
    expect(restored.userId, session.userId);
    expect(restored.username, session.username);
  });

  test('isHomeUser is true only for HOME_USER role', () {
    expect(session.isHomeUser, isTrue);
    expect(session.copyWith(role: 'COLLECTOR').isHomeUser, isFalse);
  });

  test('copyWith only changes the given fields', () {
    final updated = session.copyWith(accessToken: 'new-access');
    expect(updated.accessToken, 'new-access');
    expect(updated.refreshToken, session.refreshToken);
    expect(updated.role, session.role);
  });
}
