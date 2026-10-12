import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/features/auth/auth_controller.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';
import 'package:kabadiwala_mobile/features/collector/collector_repository.dart';
import 'package:kabadiwala_mobile/features/ewaste/ewaste_repository.dart';
import 'package:kabadiwala_mobile/features/home_user/home_user_repository.dart';
import 'package:kabadiwala_mobile/features/translation/translation_controller.dart';
import 'package:kabadiwala_mobile/features/translation/translation_storage.dart';
import 'package:kabadiwala_mobile/screens/auth_gate.dart';
import 'package:kabadiwala_mobile/screens/collector/collector_home_screen.dart';
import 'package:kabadiwala_mobile/screens/home_screen.dart';
import 'package:kabadiwala_mobile/screens/login_screen.dart';
import 'package:provider/provider.dart';

import '../test_utils/in_memory_auth_storage.dart';

http.Response _json(Map<String, dynamic> body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

Widget _wrapWithSession(AuthSession? session, AuthStatus status) {
  // Returns something parseable for whichever profile endpoint the
  // destination screen happens to call in its initState — AuthGate's own
  // routing decision is what's under test here, not those screens' data.
  final apiClient = ApiClient(
    baseUrl: 'http://test',
    client: MockClient((req) async {
      if (req.url.path == '/api/v1/collectors/me') {
        return _json({
          'user_id': 'coll-1',
          'employee_id': 'EMP-001',
          'ward_id': 'WARD-1',
          'rrr_id': null,
          'assigned_area_radius_m': null,
        }, 200);
      }
      return _json({
        'user_id': 'user-1',
        'username': 'citizen1',
        'full_name': 'Citizen One',
        'address': 'x',
        'ward_id': 'WARD-1',
        'household_lat': 1.0,
        'household_lng': 1.0,
        'upi_id': null,
      }, 200);
    }),
  );
  final authController = AuthController(
    repository: AuthRepository(apiClient: apiClient, authStorage: InMemoryAuthStorage()),
  );
  authController.status = status;
  authController.session = session;

  return MultiProvider(
    providers: [
      Provider<ApiClient>.value(value: apiClient),
      Provider<HomeUserRepository>(create: (_) => HomeUserRepository(apiClient: apiClient)),
      Provider<CollectorRepository>(create: (_) => CollectorRepository(apiClient: apiClient)),
      Provider<EwasteRepository>(create: (_) => EwasteRepository(apiClient: apiClient)),
      ChangeNotifierProvider<AuthController>.value(value: authController),
      // Both dashboards show the app-wide language setting.
      ChangeNotifierProvider<TranslationController>(
        create: (_) => TranslationController(storage: TranslationStorage()),
      ),
    ],
    child: const MaterialApp(home: AuthGate()),
  );
}

void main() {
  testWidgets('a COLLECTOR session routes to CollectorHomeScreen, never HomeScreen', (tester) async {
    const session = AuthSession(
      accessToken: 'tok', refreshToken: 'ref', role: 'COLLECTOR', userId: 'coll-1', username: 'EMP-001',
    );
    await tester.pumpWidget(_wrapWithSession(session, AuthStatus.authenticated));
    await tester.pump();

    expect(find.byType(CollectorHomeScreen), findsOneWidget);
    expect(find.byType(HomeScreen), findsNothing);
  });

  testWidgets('a HOME_USER session routes to HomeScreen, never CollectorHomeScreen', (tester) async {
    const session = AuthSession(
      accessToken: 'tok', refreshToken: 'ref', role: 'HOME_USER', userId: 'user-1', username: 'citizen1',
    );
    await tester.pumpWidget(_wrapWithSession(session, AuthStatus.authenticated));
    await tester.pump();

    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.byType(CollectorHomeScreen), findsNothing);
  });

  testWidgets('unauthenticated status shows LoginScreen regardless of any stale session data', (tester) async {
    await tester.pumpWidget(_wrapWithSession(null, AuthStatus.unauthenticated));
    await tester.pump();

    expect(find.byType(LoginScreen), findsOneWidget);
  });
}
