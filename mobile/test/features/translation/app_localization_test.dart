import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/features/auth/auth_controller.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';
import 'package:kabadiwala_mobile/features/collector/collector_repository.dart';
import 'package:kabadiwala_mobile/features/home_user/home_user_repository.dart';
import 'package:kabadiwala_mobile/features/notifications/notifications_repository.dart';
import 'package:kabadiwala_mobile/features/translation/app_localizations.dart';
import 'package:kabadiwala_mobile/features/translation/app_strings_kn.dart';
import 'package:kabadiwala_mobile/features/translation/translation_controller.dart';
import 'package:kabadiwala_mobile/features/translation/translation_language.dart';
import 'package:kabadiwala_mobile/features/translation/translation_storage.dart';
import 'package:kabadiwala_mobile/screens/auth_gate.dart';
import 'package:provider/provider.dart';

import '../../test_utils/in_memory_auth_storage.dart';

const _languageKey = 'kc_app_language';
const _legacyKey = 'kc_translation_language';
const _languageTile = Key('language_setting_tile');

/// Stands in for the device's secure storage; the SAME instance shared by
/// two controllers simulates closing and reopening the app.
class _MemoryStore implements TranslationKeyValueStore {
  final values = <String, String>{};

  @override
  Future<void> write(String key, String value) async => values[key] = value;

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> delete(String key) async => values.remove(key);
}

http.Response _json(Map<String, dynamic> body) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      200,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

/// Fake backend: logging in returns [role]; profile endpoints return data.
ApiClient _api(String role) => ApiClient(
      baseUrl: 'http://test',
      client: MockClient((request) async {
        switch (request.url.path) {
          case '/api/v1/auth/login':
            return _json({'access_token': 'acc', 'refresh_token': 'ref', 'role': role});
          case '/api/v1/auth/me':
            return _json({'user_id': 'user-1', 'username': 'user-1', 'role': role});
          case '/api/v1/collectors/me':
            return _json({'user_id': 'user-1', 'employee_id': 'EMP-001', 'ward_id': 'WARD-1'});
          case '/api/v1/home-users/me':
            return _json({
              'user_id': 'user-1',
              'username': 'citizen1',
              'full_name': 'Asha Rao',
              'address': '12 MG Road',
              'ward_id': 'WARD-1',
              'household_lat': 12.97,
              'household_lng': 77.59,
            });
          case '/api/v1/notifications/unread-count':
            return _json({'unread_count': 0});
        }
        return _json({});
      }),
    );

Future<TranslationController> _controller(_MemoryStore store) async {
  final controller = TranslationController(storage: TranslationStorage(storage: store));
  await controller.initialize();
  return controller;
}

/// The app as main.dart builds it: AuthGate (login screen until logged in)
/// under a MaterialApp whose locale follows the TranslationController.
Future<void> _pumpApp(WidgetTester tester, TranslationController translation, {String role = 'HOME_USER'}) async {
  final api = _api(role);
  final auth = AuthController(repository: AuthRepository(apiClient: api, authStorage: InMemoryAuthStorage()))
    ..status = AuthStatus.unauthenticated;
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthController>.value(value: auth),
        Provider<CollectorRepository>(create: (_) => CollectorRepository(apiClient: api)),
        Provider<HomeUserRepository>(create: (_) => HomeUserRepository(apiClient: api)),
        Provider<NotificationsRepository>(create: (_) => NotificationsRepository(apiClient: api)),
        ChangeNotifierProvider<TranslationController>.value(value: translation),
      ],
      child: Consumer<TranslationController>(
        builder: (context, controller, _) => MaterialApp(
          locale: controller.locale,
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          home: const AuthGate(),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _chooseLanguage(WidgetTester tester, String languageCode) async {
  await tester.tap(find.byKey(_languageTile));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(Key('language_option_$languageCode')));
  await tester.pumpAndSettle();
}

Future<void> _logIn(WidgetTester tester) async {
  await tester.enterText(find.byKey(const Key('login_username_field')), 'user-1');
  await tester.enterText(find.byKey(const Key('login_password_field')), 'secret123');
  await tester.tap(find.byKey(const Key('login_submit_button')));
  await tester.pumpAndSettle();
}

void main() {
  group('default language & persistence', () {
    test('only English and Kannada are offered', () {
      expect(TranslationLanguage.supported.map((l) => l.locale.languageCode), ['en', 'kn']);
      expect(TranslationLanguage.kannada.nativeName, 'ಕನ್ನಡ');
    });

    test('no saved preference -> English', () async {
      final controller = await _controller(_MemoryStore());
      expect(controller.language, TranslationLanguage.english);
      expect(controller.locale, const Locale('en'));
    });

    test('a value left by the old machine-translation selector does not force Kannada', () async {
      final store = _MemoryStore()..values[_legacyKey] = 'kan_Knda';
      final controller = await _controller(store);
      expect(controller.language, TranslationLanguage.english);
      expect(store.values[_legacyKey], 'kan_Knda'); // left untouched, just ignored
    });

    test('an unsupported saved code falls back to English', () async {
      final store = _MemoryStore()..values[_languageKey] = 'hin_Deva';
      expect((await _controller(store)).language, TranslationLanguage.english);
    });

    test('saved Kannada is restored on the next launch; English likewise', () async {
      final store = _MemoryStore();
      await (await _controller(store)).selectLanguage(TranslationLanguage.kannada.code);
      expect(store.values[_languageKey], 'kan_Knda');
      final relaunched = await _controller(store);
      expect(relaunched.language, TranslationLanguage.kannada);

      await relaunched.selectLanguage(TranslationLanguage.english.code);
      expect((await _controller(store)).language, TranslationLanguage.english);
    });
  });

  group('translations', () {
    test('Kannada table translates UI text; unknown text and English pass through', () {
      const kn = AppLocalizations(Locale('kn'), kannadaStrings);
      const en = AppLocalizations(Locale('en'), {});
      expect(kn.text('Submit E-Waste'), 'ಇ-ತ್ಯಾಜ್ಯ ಸಲ್ಲಿಸಿ');
      expect(en.text('Submit E-Waste'), 'Submit E-Waste');
      expect(kn.text('Some server message'), 'Some server message');
      expect(kn.format('{count} recyclers have bid', {'count': 3}), '3 ಮರುಬಳಕೆದಾರರು ಬಿಡ್ ಮಾಡಿದ್ದಾರೆ');
    });

    test('every tr()/trf() literal in lib/ has a Kannada translation', () {
      final literal = RegExp(r"""\btrf?\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")""");
      final missing = <String>{};
      for (final file in Directory('lib').listSync(recursive: true).whereType<File>()) {
        if (!file.path.endsWith('.dart')) continue;
        final code = file.readAsStringSync().replaceAll(RegExp(r'^\s*//.*$', multiLine: true), '');
        for (final match in literal.allMatches(code)) {
          final text = (match.group(1) ?? match.group(2)!).replaceAll(r"\'", "'");
          if (text.contains(r'$')) continue; // interpolated — not a literal key
          if (!kannadaStrings.containsKey(text)) missing.add('$text  (${file.path})');
        }
      }
      expect(missing, isEmpty, reason: 'Add these to app_strings_kn.dart');
    });

    test('translations are Kannada script and keep their {placeholders}', () {
      final kannadaScript = RegExp('[ಀ-೿]');
      final placeholder = RegExp(r'\{\w+\}');
      kannadaStrings.forEach((english, kannada) {
        expect(kannadaScript.hasMatch(kannada), isTrue, reason: english);
        expect(
          placeholder.allMatches(kannada).map((m) => m[0]).toSet(),
          placeholder.allMatches(english).map((m) => m[0]).toSet(),
          reason: english,
        );
      });
    });
  });

  group('language selection on the login / role-selection screen', () {
    testWidgets('login screen opens in English and switches immediately both ways', (tester) async {
      final store = _MemoryStore();
      await _pumpApp(tester, await _controller(store));

      expect(find.byKey(_languageTile), findsOneWidget);
      expect(find.text('App Language'), findsOneWidget);
      expect(find.text('Home User Login'), findsOneWidget);
      expect(find.text('Log In'), findsOneWidget);

      await _chooseLanguage(tester, 'kn');
      expect(find.text('ಆ್ಯಪ್ ಭಾಷೆ'), findsOneWidget);
      expect(find.text('ಮನೆ ಬಳಕೆದಾರರ ಲಾಗಿನ್'), findsOneWidget);
      expect(find.text('ಲಾಗಿನ್ ಮಾಡಿ'), findsOneWidget);
      expect(find.text('ಸಂಗ್ರಾಹಕ'), findsOneWidget); // role selector
      expect(find.text('Home User Login'), findsNothing);
      expect(store.values[_languageKey], 'kan_Knda');

      await _chooseLanguage(tester, 'en');
      expect(find.text('Home User Login'), findsOneWidget);
      expect(find.text('Log In'), findsOneWidget);
      expect(store.values[_languageKey], 'eng_Latn');
    });

    testWidgets('Kannada chosen before login applies to the Home User app; no language row on dashboard',
        (tester) async {
      await _pumpApp(tester, await _controller(_MemoryStore()), role: 'HOME_USER');
      await _chooseLanguage(tester, 'kn');
      await _logIn(tester);

      expect(find.text('ನನ್ನ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್'), findsOneWidget);
      expect(find.text('ಇ-ತ್ಯಾಜ್ಯ ಸಲ್ಲಿಸಿ'), findsOneWidget);
      expect(find.text('Asha Rao'), findsOneWidget); // user data unchanged
      expect(find.byKey(_languageTile), findsNothing);
      expect(find.text('ಆ್ಯಪ್ ಭಾಷೆ'), findsNothing);
      expect(find.byKey(const Key('language_button')), findsNothing); // old globe icon
    });

    testWidgets('Kannada chosen before login applies to the Collector app; no language row on dashboard',
        (tester) async {
      await _pumpApp(tester, await _controller(_MemoryStore()), role: 'COLLECTOR');
      await tester.tap(find.text('Collector')); // role selector segment
      await tester.pumpAndSettle();
      await _chooseLanguage(tester, 'kn');
      expect(find.text('ಸಂಗ್ರಾಹಕರ ಲಾಗಿನ್'), findsOneWidget);
      await _logIn(tester);

      expect(find.text('ಸಂಗ್ರಾಹಕರ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್'), findsOneWidget);
      expect(find.text('ಬಾಕಿ ಇರುವ ಸಂಗ್ರಹಣೆಗಳು'), findsOneWidget);
      expect(find.text('ಉದ್ಯೋಗಿ ಐಡಿ: EMP-001'), findsOneWidget);
      expect(find.byKey(_languageTile), findsNothing);
      expect(find.text('ಆ್ಯಪ್ ಭಾಷೆ'), findsNothing);
    });

    testWidgets('English (default) applies after login too', (tester) async {
      await _pumpApp(tester, await _controller(_MemoryStore()), role: 'COLLECTOR');
      await _logIn(tester);
      expect(find.text('Collector Dashboard'), findsOneWidget);
      expect(find.byKey(_languageTile), findsNothing);
    });

    testWidgets('choice survives a simulated app restart', (tester) async {
      final store = _MemoryStore();
      await _pumpApp(tester, await _controller(store));
      await _chooseLanguage(tester, 'kn');

      // Close and reopen: a brand-new controller on the same device storage.
      await tester.pumpWidget(const SizedBox());
      await _pumpApp(tester, await _controller(store));
      expect(find.text('ಮನೆ ಬಳಕೆದಾರರ ಲಾಗಿನ್'), findsOneWidget);
      expect(find.text('ಕನ್ನಡ'), findsOneWidget); // current choice shown on the tile

      await _logIn(tester);
      expect(find.text('ನನ್ನ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್'), findsOneWidget);
    });
  });
}
