import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/core/auth_storage.dart';
import 'package:kabadiwala_mobile/features/auth/auth_controller.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';
import 'package:kabadiwala_mobile/features/rewards/rewards_repository.dart';
import 'package:kabadiwala_mobile/screens/financial_history_screen.dart';
import 'package:provider/provider.dart';

http.Response _json(Map<String, dynamic> body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

AuthController _auth() {
  final controller = AuthController(
    repository: AuthRepository(
      apiClient: ApiClient(baseUrl: 'http://test', client: MockClient((_) async => _json({}, 200))),
      authStorage: AuthStorage(),
    ),
  );
  controller.session = const AuthSession(
    accessToken: 'token',
    refreshToken: 'refresh',
    role: 'HOME_USER',
    userId: 'user-1',
    username: 'user-1',
  );
  controller.status = AuthStatus.authenticated;
  return controller;
}

void main() {
  testWidgets('shows persisted summary and reward transaction history', (tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<AuthController>.value(value: _auth()),
          Provider<RewardsRepository>(
            create: (_) => RewardsRepository(
              apiClient: ApiClient(
                baseUrl: 'http://test',
                client: MockClient((request) async {
                  if (request.url.path.endsWith('/summary/mine')) {
                    return _json({
                      'completed_credits': '5.00',
                      'completed_redemptions': '0',
                      'pending_amount': '0',
                      'failed_count': 0,
                    }, 200);
                  }
                  return _json({
                    'transactions': [
                      {
                        'txn_id': 'txn-1',
                        'home_user_id': 'user-1',
                        'reward_id': 'reward-1',
                        'type': 'CREDIT',
                        'amount': '5.00',
                        'status': 'SUCCEEDED',
                        'created_at': '2026-09-01T00:00:00',
                      },
                    ],
                    'has_more': false,
                  }, 200);
                }),
              ),
            ),
          ),
        ],
        child: const MaterialApp(home: FinancialHistoryScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Persisted financial summary'), findsOneWidget);
    expect(find.text('Completed reward credits'), findsOneWidget);
    expect(find.text('+₹5.00'), findsOneWidget);
  });
}
