import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/core/api_exception.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';

import '../../test_utils/in_memory_auth_storage.dart';

const _stubSession = AuthSession(
  accessToken: 'stale-acc',
  refreshToken: 'stale-ref',
  role: 'HOME_USER',
  userId: 'user-1',
  username: 'citizen1',
);

http.Response _json(Map<String, dynamic> body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

void main() {
  group('AuthRepository.login', () {
    test('on success, fetches /me and persists the combined session', () async {
      final storage = InMemoryAuthStorage();
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            if (req.url.path == '/api/v1/auth/login') {
              return _json({'access_token': 'acc-1', 'refresh_token': 'ref-1', 'role': 'HOME_USER'}, 200);
            }
            if (req.url.path == '/api/v1/auth/me') {
              return _json({'user_id': 'user-1', 'username': 'citizen1', 'role': 'HOME_USER'}, 200);
            }
            throw StateError('unexpected path ${req.url.path}');
          }),
        ),
      );

      final session = await repo.login('citizen1', 'password123');

      expect(session.accessToken, 'acc-1');
      expect(session.userId, 'user-1');
      expect(session.username, 'citizen1');
      final stored = await storage.loadSession();
      expect(stored?.accessToken, 'acc-1');
    });

    test('accepts a COLLECTOR role and persists the session (Phase 4)', () async {
      final storage = InMemoryAuthStorage();
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            if (req.url.path == '/api/v1/auth/login') {
              return _json({'access_token': 'acc-1', 'refresh_token': 'ref-1', 'role': 'COLLECTOR'}, 200);
            }
            return _json({'user_id': 'coll-1', 'username': 'EMP-001', 'role': 'COLLECTOR'}, 200);
          }),
        ),
      );

      final session = await repo.login('EMP-001', 'password123');
      expect(session.role, 'COLLECTOR');
      expect(await storage.loadSession(), isNotNull);
    });

    test('rejects a role that is neither HOME_USER nor COLLECTOR, without persisting a session', () async {
      final storage = InMemoryAuthStorage();
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({'access_token': 'acc-1', 'refresh_token': 'ref-1', 'role': 'RECYCLER'}, 200);
          }),
        ),
      );

      expect(() => repo.login('rcy1', 'password123'), throwsA(isA<WrongRoleException>()));
      expect(await storage.loadSession(), isNull);
    });

    test('propagates invalid-credentials errors from the backend', () async {
      final storage = InMemoryAuthStorage();
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({'success': false, 'error_code': 'INVALID_CREDENTIALS', 'message': 'Invalid username or password.'}, 401);
          }),
        ),
      );

      expect(
        () => repo.login('citizen1', 'wrong'),
        throwsA(isA<ApiException>().having((e) => e.errorCode, 'errorCode', 'INVALID_CREDENTIALS')),
      );
    });
  });

  group('AuthRepository.restoreSession', () {
    test('returns null when nothing is stored', () async {
      final storage = InMemoryAuthStorage();
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(baseUrl: 'http://test', client: MockClient((req) async => _json({}, 200))),
      );
      expect(await repo.restoreSession(), isNull);
    });

    test('a still-valid access token is refreshed against /me directly', () async {
      final storage = InMemoryAuthStorage();
      await storage.saveSession(_stubSession);
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            expect(req.url.path, '/api/v1/auth/me');
            return _json({'user_id': 'user-1', 'username': 'citizen1', 'role': 'HOME_USER'}, 200);
          }),
        ),
      );
      final session = await repo.restoreSession();
      expect(session?.accessToken, _stubSession.accessToken);
    });

    test('an expired access token is refreshed via /auth/refresh, then /me', () async {
      final storage = InMemoryAuthStorage();
      await storage.saveSession(_stubSession);
      var refreshCalled = false;
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            if (req.url.path == '/api/v1/auth/me' && !refreshCalled) {
              return _json({'success': false, 'error_code': 'INVALID_TOKEN', 'message': 'Invalid.'}, 401);
            }
            if (req.url.path == '/api/v1/auth/refresh') {
              refreshCalled = true;
              return _json({'access_token': 'new-acc'}, 200);
            }
            if (req.url.path == '/api/v1/auth/me' && refreshCalled) {
              return _json({'user_id': 'user-1', 'username': 'citizen1', 'role': 'HOME_USER'}, 200);
            }
            throw StateError('unexpected call');
          }),
        ),
      );
      final session = await repo.restoreSession();
      expect(session?.accessToken, 'new-acc');
    });

    test('when refresh also fails, storage is cleared and null is returned', () async {
      final storage = InMemoryAuthStorage();
      await storage.saveSession(_stubSession);
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            if (req.url.path == '/api/v1/auth/me') {
              return _json({'success': false, 'error_code': 'INVALID_TOKEN', 'message': 'Invalid.'}, 401);
            }
            return _json({'success': false, 'error_code': 'INVALID_TOKEN', 'message': 'Invalid.'}, 401);
          }),
        ),
      );
      final session = await repo.restoreSession();
      expect(session, isNull);
      expect(await storage.loadSession(), isNull);
    });
  });

  group('AuthRepository.logout', () {
    test('clears local storage even if the server call fails', () async {
      final storage = InMemoryAuthStorage();
      await storage.saveSession(_stubSession);
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async => _json({'success': false, 'error_code': 'INVALID_TOKEN', 'message': 'x'}, 401)),
        ),
      );
      await repo.logout(_stubSession);
      expect(await storage.loadSession(), isNull);
    });
  });

  group('AuthRepository.refreshAccessToken (offline-submission sync)', () {
    test('stores and returns the session with the new access token', () async {
      final storage = InMemoryAuthStorage();
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            expect(req.url.path, '/api/v1/auth/refresh');
            expect(jsonDecode(req.body), {'refresh_token': 'stale-ref'});
            return _json({'access_token': 'fresh-acc'}, 200);
          }),
        ),
      );

      final refreshed = await repo.refreshAccessToken(_stubSession);

      expect(refreshed?.accessToken, 'fresh-acc');
      expect(refreshed?.refreshToken, 'stale-ref');
      expect((await storage.loadSession())?.accessToken, 'fresh-acc');
    });

    test('returns null (session untouched) when refresh is refused or offline', () async {
      final storage = InMemoryAuthStorage();
      await storage.saveSession(_stubSession);
      final repo = AuthRepository(
        authStorage: storage,
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((_) async => throw http.ClientException('offline')),
        ),
      );

      expect(await repo.refreshAccessToken(_stubSession), isNull);
      expect((await storage.loadSession())?.accessToken, 'stale-acc');
    });
  });
}
