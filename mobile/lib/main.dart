import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/api_client.dart';
import 'core/auth_storage.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/auth_repository.dart';
import 'features/collector/collector_repository.dart';
import 'features/ewaste/ewaste_repository.dart';
import 'features/ewaste/offline/offline_submission_store.dart';
import 'features/ewaste/offline/offline_submission_sync.dart';
import 'features/ewaste/offline/offline_sync_binder.dart';
import 'features/home_user/home_user_repository.dart';
import 'features/lots/lots_repository.dart';
import 'features/rewards/rewards_repository.dart';
import 'features/notifications/notifications_repository.dart';
import 'features/translation/app_localizations.dart';
import 'features/translation/translation_controller.dart';
import 'features/translation/translation_storage.dart';
import 'features/translation/translation_text.dart';
import 'shared/theme.dart';
import 'screens/auth_gate.dart';

/// Lets background work (offline-submission sync) show an in-app message
/// regardless of which screen is currently open.
final scaffoldMessengerKey = GlobalKey<ScaffoldMessengerState>();

void main() {
  runApp(const KabadiwalaHomeUserApp());
}

class KabadiwalaHomeUserApp extends StatelessWidget {
  const KabadiwalaHomeUserApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiClient>(create: (_) => ApiClient()),
        Provider<AuthStorage>(create: (_) => AuthStorage()),
        Provider<AuthRepository>(
          create: (ctx) => AuthRepository(
            apiClient: ctx.read<ApiClient>(),
            authStorage: ctx.read<AuthStorage>(),
          ),
        ),
        Provider<HomeUserRepository>(
          create: (ctx) => HomeUserRepository(apiClient: ctx.read<ApiClient>()),
        ),
        Provider<CollectorRepository>(
          create: (ctx) => CollectorRepository(apiClient: ctx.read<ApiClient>()),
        ),
        Provider<EwasteRepository>(
          create: (ctx) => EwasteRepository(apiClient: ctx.read<ApiClient>()),
        ),
        Provider<LotsRepository>(
          create: (ctx) => LotsRepository(apiClient: ctx.read<ApiClient>()),
        ),
        Provider<RewardsRepository>(
          create: (ctx) => RewardsRepository(apiClient: ctx.read<ApiClient>()),
        ),
        Provider<NotificationsRepository>(
          create: (ctx) => NotificationsRepository(apiClient: ctx.read<ApiClient>()),
        ),
        Provider<TranslationStorage>(create: (_) => TranslationStorage()),
        ChangeNotifierProvider<TranslationController>(
          create: (ctx) => TranslationController(
            storage: ctx.read<TranslationStorage>(),
          )..initialize(),
        ),
        ChangeNotifierProvider<AuthController>(
          create: (ctx) => AuthController(repository: ctx.read<AuthRepository>())..restore(),
        ),
        Provider<OfflineSubmissionSync>(
          create: (ctx) {
            final auth = ctx.read<AuthController>();
            return OfflineSubmissionSync(
              store: OfflineSubmissionStore(),
              repository: ctx.read<EwasteRepository>(),
              currentSession: () => auth.session,
              refreshAccessToken: auth.refreshAccessToken,
              onSynced: (_) => scaffoldMessengerKey.currentState?.showSnackBar(
                SnackBar(
                  content: Text(
                    scaffoldMessengerKey.currentContext?.tr(offlineSyncedMessage) ?? offlineSyncedMessage,
                  ),
                ),
              ),
            );
          },
        ),
      ],
      child: Consumer<TranslationController>(
        builder: (context, translation, _) => MaterialApp(
        title: 'Kabadiwala Connect',
        debugShowCheckedModeBanner: false,
        theme: buildAppTheme(),
        // The selected language drives every screen: app strings via
        // AppLocalizations, Material widget text via the Global delegates.
        locale: translation.locale,
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        scaffoldMessengerKey: scaffoldMessengerKey,
        builder: (context, child) =>
            kIsWeb ? child! : OfflineSyncBinder(child: child!),
        home: const AuthGate(),
        ),
      ),
    );
  }
}
