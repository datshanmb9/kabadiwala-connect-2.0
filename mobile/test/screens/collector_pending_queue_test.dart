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
import 'package:kabadiwala_mobile/features/ewaste/ewaste_repository.dart';
import 'package:kabadiwala_mobile/screens/collector/collector_pending_queue_screen.dart';
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
    role: 'COLLECTOR',
    userId: 'collector-1',
    username: 'EMP-001',
  );
  controller.status = AuthStatus.authenticated;
  return controller;
}

void main() {
  testWidgets('pending collections show the backend price estimate and total range', (tester) async {
    final requestedPaths = <String>[];
    Map<String, String>? trendQuery;
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<AuthController>.value(value: _auth()),
          Provider<EwasteRepository>(
            create: (_) => EwasteRepository(
              apiClient: ApiClient(
                baseUrl: 'http://test',
                client: MockClient((request) async {
                  requestedPaths.add(request.url.path);
                  if (request.url.path == '/api/v1/pricing/trend') {
                    trendQuery = request.url.queryParameters;
                    return _json({
                      'item': 'e-waste-small-appliances',
                      'ward_id': 'WARD-1',
                      'scope': 'ward',
                      'window_days': 90,
                      'min_points': 4,
                      'points': [
                        {'date': '2026-09-01', 'price_per_kg': 100.0, 'sales': 1},
                        {'date': '2026-09-05', 'price_per_kg': 104.0, 'sales': 1},
                        {'date': '2026-09-12', 'price_per_kg': 118.0, 'sales': 2},
                        {'date': '2026-09-20', 'price_per_kg': 125.0, 'sales': 1},
                      ],
                      'trend': 'increasing',
                      'change_percent': 19.12,
                      'latest_price_per_kg': 125.0,
                      'latest_date': '2026-09-20',
                    }, 200);
                  }
                  return _json({
                    'success': true,
                    'submissions': [
                      {
                        'submission_id': 'sub-12345678',
                        'home_user_id': 'user-1',
                        'ward_id': 'WARD-1',
                        'status': 'WAITING_FOR_COLLECTION',
                        'price_estimate': {
                          'predicted_price_per_kg': 109.12,
                          'min_price': 98.21,
                          'max_price': 120.03,
                          'estimated_total_value': 43.65,
                          'estimated_total_min': 39.28,
                          'estimated_total_max': 48.01,
                          'product_type': 'e-waste-small-appliances',
                          'condition': 'Used',
                          'weight_kg': 0.40,
                          'is_estimate': true,
                        },
                      },
                    ],
                  }, 200);
                }),
              ),
            ),
          ),
        ],
        child: const MaterialApp(home: CollectorPendingQueueScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Estimated price: ₹98.21 – ₹120.03 / kg'), findsOneWidget);
    expect(find.text('Estimated total: ₹39.28 – ₹48.01 (0.40 kg)'), findsOneWidget);
    // Backend trend for the same item/ward is shown under the estimate.
    expect(find.text('Price trend: Increasing · Latest market price: ₹125.00/kg'), findsOneWidget);
    expect(trendQuery, {'item': 'e-waste-small-appliances', 'ward_id': 'WARD-1'});
    // The ML price model is never called from the UI.
    expect(requestedPaths, ['/api/v1/ewaste/submissions/pending', '/api/v1/pricing/trend']);
  });
}
