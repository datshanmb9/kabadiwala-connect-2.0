import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/features/auth/auth_controller.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';

import '../../test_utils/in_memory_auth_storage.dart';

http.Response _json(Map<String, dynamic> body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

void main() {
  test('successful login moves status to authenticated and clears any prior error', () async {
    final controller = AuthController(
      repository: AuthRepository(
        authStorage: InMemoryAuthStorage(),
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            if (req.url.path == '/api/v1/auth/login') {
              return _json({'access_token': 'acc-1', 'refresh_token': 'ref-1', 'role': 'HOME_USER'}, 200);
            }
            return _json({'user_id': 'user-1', 'username': 'citizen1', 'role': 'HOME_USER'}, 200);
          }),
        ),
      ),
    );

    final ok = await controller.login('citizen1', 'password123');

    expect(ok, isTrue);
    expect(controller.status, AuthStatus.authenticated);
    expect(controller.session?.username, 'citizen1');
    expect(controller.errorMessage, isNull);
  });

  test('failed login moves status to unauthenticated and sets a readable error message', () async {
    final controller = AuthController(
      repository: AuthRepository(
        authStorage: InMemoryAuthStorage(),
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({'success': false, 'error_code': 'INVALID_CREDENTIALS', 'message': 'Invalid username or password.'}, 401);
          }),
        ),
      ),
    );

    final ok = await controller.login('citizen1', 'wrong');

    expect(ok, isFalse);
    expect(controller.status, AuthStatus.unauthenticated);
    expect(controller.session, isNull);
    expect(controller.errorMessage, 'Invalid username or password.');
  });

  test('collector login moves status to authenticated with role COLLECTOR (Phase 4)', () async {
    final controller = AuthController(
      repository: AuthRepository(
        authStorage: InMemoryAuthStorage(),
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            if (req.url.path == '/api/v1/auth/login') {
              return _json({'access_token': 'acc-1', 'refresh_token': 'ref-1', 'role': 'COLLECTOR'}, 200);
            }
            return _json({'user_id': 'coll-1', 'username': 'EMP-001', 'role': 'COLLECTOR'}, 200);
          }),
        ),
      ),
    );

    final ok = await controller.login('EMP-001', 'password123');

    expect(ok, isTrue);
    expect(controller.status, AuthStatus.authenticated);
    expect(controller.session?.role, 'COLLECTOR');
  });

  test('a role outside HOME_USER/COLLECTOR is rejected client-side with a clear message', () async {
    final controller = AuthController(
      repository: AuthRepository(
        authStorage: InMemoryAuthStorage(),
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({'access_token': 'acc-1', 'refresh_token': 'ref-1', 'role': 'RECYCLER'}, 200);
          }),
        ),
      ),
    );

    final ok = await controller.login('rcy1', 'password123');

    expect(ok, isFalse);
    expect(controller.status, AuthStatus.unauthenticated);
    expect(controller.errorMessage, contains('Home Users and Collectors only'));
  });

  test('restore() with nothing stored ends in unauthenticated, not stuck loading', () async {
    final controller = AuthController(
      repository: AuthRepository(
        authStorage: InMemoryAuthStorage(),
        apiClient: ApiClient(baseUrl: 'http://test', client: MockClient((req) async => _json({}, 200))),
      ),
    );

    await controller.restore();

    expect(controller.status, AuthStatus.unauthenticated);
    expect(controller.isAuthenticated, isFalse);
  });

  test('logout clears session immediately, regardless of the server call outcome', () async {
    final storage = InMemoryAuthStorage();
    final controller = AuthController(
      repository: AuthRepository(
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
            return _json({'success': false, 'error_code': 'INVALID_TOKEN', 'message': 'x'}, 401);
          }),
        ),
      ),
    );
    await controller.login('citizen1', 'password123');
    expect(controller.isAuthenticated, isTrue);

    await controller.logout();

    expect(controller.isAuthenticated, isFalse);
    expect(controller.session, isNull);
    expect(await storage.loadSession(), isNull);
  });
}
