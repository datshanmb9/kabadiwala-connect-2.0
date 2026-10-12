import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/features/auth/auth_controller.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';
import 'package:kabadiwala_mobile/features/ewaste/ewaste_repository.dart';
import 'package:kabadiwala_mobile/features/home_user/home_user_repository.dart';
import 'package:kabadiwala_mobile/features/translation/translation_controller.dart';
import 'package:kabadiwala_mobile/features/translation/translation_storage.dart';
import 'package:kabadiwala_mobile/screens/login_screen.dart';
import 'package:kabadiwala_mobile/screens/register_screen.dart';
import 'package:provider/provider.dart';

import '../test_utils/in_memory_auth_storage.dart';

Widget _wrap(Widget child, ApiClient apiClient) {
  return MultiProvider(
    providers: [
      Provider<ApiClient>.value(value: apiClient),
      Provider<AuthRepository>(
        create: (_) => AuthRepository(apiClient: apiClient, authStorage: InMemoryAuthStorage()),
      ),
      Provider<HomeUserRepository>(create: (_) => HomeUserRepository(apiClient: apiClient)),
      Provider<EwasteRepository>(create: (_) => EwasteRepository(apiClient: apiClient)),
      ChangeNotifierProvider<AuthController>(
        create: (ctx) => AuthController(repository: ctx.read<AuthRepository>()),
      ),
      // The login screen shows the app-wide language setting.
      ChangeNotifierProvider<TranslationController>(
        create: (_) => TranslationController(storage: TranslationStorage()),
      ),
    ],
    child: MaterialApp(home: child),
  );
}

Widget _wrapWithController(Widget child, ApiClient apiClient, AuthController controller) {
  return MultiProvider(
    providers: [
      Provider<ApiClient>.value(value: apiClient),
      Provider<HomeUserRepository>(create: (_) => HomeUserRepository(apiClient: apiClient)),
      Provider<EwasteRepository>(create: (_) => EwasteRepository(apiClient: apiClient)),
      ChangeNotifierProvider<AuthController>.value(value: controller),
      // The login screen shows the app-wide language setting.
      ChangeNotifierProvider<TranslationController>(
        create: (_) => TranslationController(storage: TranslationStorage()),
      ),
    ],
    child: MaterialApp(home: child),
  );
}

void main() {
  testWidgets('shows an inline error banner when login fails', (tester) async {
    final apiClient = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((req) async {
        return http.Response(
          '{"success": false, "error_code": "INVALID_CREDENTIALS", "message": "Invalid username or password."}',
          401,
          headers: {'content-type': 'application/json'},
        );
      }),
    );

    await tester.pumpWidget(_wrap(const LoginScreen(), apiClient));

    await tester.enterText(find.byKey(const Key('login_username_field')), 'citizen1');
    await tester.enterText(find.byKey(const Key('login_password_field')), 'wrongpassword');
    await tester.tap(find.byKey(const Key('login_submit_button')));
    await tester.pumpAndSettle();

    expect(find.text('Invalid username or password.'), findsOneWidget);
  });

  testWidgets('empty form shows validation errors and never calls the API', (tester) async {
    var callCount = 0;
    final apiClient = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((req) async {
        callCount++;
        return http.Response('{}', 200);
      }),
    );

    await tester.pumpWidget(_wrap(const LoginScreen(), apiClient));
    await tester.tap(find.byKey(const Key('login_submit_button')));
    await tester.pumpAndSettle();

    expect(callCount, 0);
    expect(find.text('Username is required'), findsOneWidget);
  });

  testWidgets('tapping "Register" navigates to the registration screen', (tester) async {
    final apiClient = ApiClient(
      baseUrl: 'http://test',
      client: MockClient((req) async {
        return http.Response('{"success": true, "wards": []}', 200, headers: {'content-type': 'application/json'});
      }),
    );

    await tester.pumpWidget(_wrap(const LoginScreen(), apiClient));
    // The form scrolls; the language card above it can push the link below
    // the fold on the small test surface.
    await tester.ensureVisible(find.text("Don't have an account? Register"));
    await tester.pumpAndSettle();
    await tester.tap(find.text("Don't have an account? Register"));
    await tester.pumpAndSettle();

    expect(find.byType(RegisterScreen), findsOneWidget);
  });

  group('login portal selector (Phase 4 fix)', () {
    ApiClient neverCalledApiClient() => ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            fail('API should not be called by merely toggling the portal selector');
          }),
        );

    testWidgets('defaults to the Home User heading, with the Register link visible', (tester) async {
      await tester.pumpWidget(_wrap(const LoginScreen(), neverCalledApiClient()));

      expect(find.text('Home User Login'), findsOneWidget);
      expect(find.text('Collector Login'), findsNothing);
      expect(find.text("Don't have an account? Register"), findsOneWidget);
      expect(find.widgetWithText(TextFormField, 'Username'), findsOneWidget);
    });

    testWidgets('selecting Collector switches the heading, hides Register, and relabels the username field',
        (tester) async {
      await tester.pumpWidget(_wrap(const LoginScreen(), neverCalledApiClient()));

      await tester.tap(find.text('Collector'));
      await tester.pumpAndSettle();

      expect(find.text('Collector Login'), findsOneWidget);
      expect(find.text('Home User Login'), findsNothing);
      expect(find.text("Don't have an account? Register"), findsNothing);
      expect(find.widgetWithText(TextFormField, 'Employee ID'), findsOneWidget);
    });

    testWidgets('switching back to Home User restores the original heading and Register link', (tester) async {
      await tester.pumpWidget(_wrap(const LoginScreen(), neverCalledApiClient()));

      await tester.tap(find.text('Collector'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Home User'));
      await tester.pumpAndSettle();

      expect(find.text('Home User Login'), findsOneWidget);
      expect(find.text("Don't have an account? Register"), findsOneWidget);
    });

    testWidgets('the portal selector is purely cosmetic: login still routes on the actual returned role',
        (tester) async {
      // Selects the Collector portal but the backend returns HOME_USER —
      // this must still succeed, proving the selector never gates or
      // second-guesses the backend's own role decision.
      final apiClient = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          if (req.url.path == '/api/v1/auth/login') {
            return http.Response(
              '{"access_token": "acc-1", "refresh_token": "ref-1", "role": "HOME_USER"}',
              200,
              headers: {'content-type': 'application/json'},
            );
          }
          return http.Response(
            '{"user_id": "user-1", "username": "citizen1", "role": "HOME_USER"}',
            200,
            headers: {'content-type': 'application/json'},
          );
        }),
      );
      final controller = AuthController(
        repository: AuthRepository(apiClient: apiClient, authStorage: InMemoryAuthStorage()),
      );

      await tester.pumpWidget(_wrapWithController(const LoginScreen(), apiClient, controller));
      await tester.tap(find.text('Collector'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const Key('login_username_field')), 'citizen1');
      await tester.enterText(find.byKey(const Key('login_password_field')), 'password123');
      await tester.tap(find.byKey(const Key('login_submit_button')));
      await tester.pumpAndSettle();

      expect(controller.isAuthenticated, isTrue);
      expect(controller.session?.role, 'HOME_USER');
      expect(controller.errorMessage, isNull);
    });
  });
}
