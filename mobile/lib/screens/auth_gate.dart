import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/auth/auth_controller.dart';
import '../shared/state_views.dart';
import 'collector/collector_home_screen.dart';
import 'home_screen.dart';
import 'login_screen.dart';

/// Root of the app: watches AuthController and renders the login flow or
/// the correct role's dashboard. This is the ONE place that picks between
/// the two separate navigation graphs (Section 2 of the architecture doc:
/// "two entirely separate navigation graphs... selected once at login
/// based on the role returned by the backend") — chosen from
/// `session.role` on the verified, server-confirmed session, never from
/// any locally-editable flag. Screens elsewhere never re-check this.
class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    switch (auth.status) {
      case AuthStatus.unknown:
      case AuthStatus.working:
        return const Scaffold(body: LoadingView(message: 'Loading…'));
      case AuthStatus.authenticated:
        return switch (auth.session!.role) {
          'COLLECTOR' => const CollectorHomeScreen(),
          _ => const HomeScreen(),
        };
      case AuthStatus.unauthenticated:
        return const LoginScreen();
    }
  }
}
