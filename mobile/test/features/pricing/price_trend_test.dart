import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/features/auth/auth_controller.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';
import 'package:kabadiwala_mobile/features/ewaste/ewaste_repository.dart';
import 'package:kabadiwala_mobile/features/lots/lots_repository.dart';
import 'package:kabadiwala_mobile/features/pricing/price_trend.dart';
import 'package:kabadiwala_mobile/features/pricing/widgets/price_trend_card.dart';
import 'package:kabadiwala_mobile/screens/collector/collector_lot_detail_screen.dart';
import 'package:kabadiwala_mobile/screens/submission_detail_screen.dart';
import 'package:provider/provider.dart';

import '../../test_utils/in_memory_auth_storage.dart';

Map<String, dynamic> _trendJson({String trend = 'increasing', List<List<Object>>? points}) {
  final pts = points ??
      [
        ['2026-09-01', 480.0],
        ['2026-09-08', 490.0],
        ['2026-09-15', 505.0],
        ['2026-09-22', 510.0],
      ];
  return {
    'item': 'Laptop',
    'ward_id': 'WARD-1',
    'scope': 'ward',
    'window_days': 90,
    'min_points': 4,
    'points': [
      for (final p in pts) {'date': p[0], 'price_per_kg': p[1], 'sales': 1},
    ],
    'trend': trend,
    'change_percent': trend == 'insufficient_data' ? null : 4.08,
    'latest_price_per_kg': pts.isEmpty ? null : pts.last[1],
    'latest_date': pts.isEmpty ? null : pts.last[0],
  };
}

const _insufficient = {
  'item': 'Laptop',
  'ward_id': 'WARD-1',
  'scope': 'ward',
  'window_days': 90,
  'min_points': 4,
  'points': [],
  'trend': 'insufficient_data',
  'change_percent': null,
  'latest_price_per_kg': null,
  'latest_date': null,
};

const _estimate = {
  'predicted_price_per_kg': 487.61,
  'min_price': 438.85,
  'max_price': 536.37,
  'estimated_total_value': 195.04,
  'estimated_total_min': 175.54,
  'estimated_total_max': 214.55,
  'product_type': 'Laptop',
  'condition': 'Used',
  'weight_kg': 0.4,
  'is_estimate': true,
};

/// Fake backend; [trend] is what GET /pricing/trend returns (null -> 500).
class _Backend {
  final Map<String, dynamic>? trend;
  final paths = <String>[];
  Map<String, String>? trendQuery;

  _Backend(this.trend);

  late final ApiClient api = ApiClient(
    baseUrl: 'http://test',
    client: MockClient((request) async {
      paths.add(request.url.path);
      final path = request.url.path;
      if (path == '/api/v1/pricing/trend') {
        trendQuery = request.url.queryParameters;
        return trend == null ? _json({'success': false, 'error_code': 'X', 'message': 'down'}, 500) : _json(trend!);
      }
      if (path == '/api/v1/ewaste/submissions/sub-1') {
        return _json({
          'submission_id': 'sub-1',
          'home_user_id': 'u-1',
          'ward_id': 'WARD-1',
          'status': 'WAITING_FOR_COLLECTION',
          'home_ts': '2026-09-20T10:00:00',
          'category': 'Laptop',
          'price_estimate': _estimate,
        });
      }
      if (path == '/api/v1/lots/lot-00000001') {
        return _json({
          'lot_id': 'lot-00000001',
          'ward_id': 'WARD-1',
          'category': 'Laptop',
          'item_ids': ['sub-1'],
          'status': 'LISTED_FOR_BIDDING',
          'total_weight_kg': 0.4,
        });
      }
      if (path == '/api/v1/lots/lot-00000001/bids') return _json({'bids': []});
      return _json({});
    }),
  );

  static http.Response _json(Map<String, dynamic> body, [int status = 200]) =>
      http.Response.bytes(utf8.encode(jsonEncode(body)), status, headers: {'content-type': 'application/json; charset=utf-8'});
}

Future<void> _pump(WidgetTester tester, _Backend backend, Widget screen, {String role = 'HOME_USER'}) async {
  final auth = AuthController(repository: AuthRepository(apiClient: backend.api, authStorage: InMemoryAuthStorage()))
    ..session = AuthSession(accessToken: 'tok', refreshToken: 'ref', role: role, userId: 'u-1', username: 'u-1')
    ..status = AuthStatus.authenticated;
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthController>.value(value: auth),
        Provider<EwasteRepository>(create: (_) => EwasteRepository(apiClient: backend.api)),
        Provider<LotsRepository>(create: (_) => LotsRepository(apiClient: backend.api)),
      ],
      child: MaterialApp(home: screen),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  group('PriceTrend model', () {
    test('parses backend points in order and exposes the latest price', () {
      final trend = PriceTrend.fromJson(_trendJson());
      expect(trend.points.map((p) => p.pricePerKg), [480.0, 490.0, 505.0, 510.0]);
      expect(trend.points.first.date, DateTime(2026, 9, 1));
      expect(trend.latestPricePerKg, 510.0);
      expect(trend.hasTrend, isTrue);
      expect(trend.totalSales, 4);
    });

    test('insufficient data never counts as a trend', () {
      expect(PriceTrend.fromJson(_insufficient).hasTrend, isFalse);
      // Even with some real points, no direction is claimed without enough history.
      final partial = PriceTrend.fromJson(_trendJson(trend: 'insufficient_data', points: [
        ['2026-09-01', 480.0],
        ['2026-09-02', 500.0],
      ]));
      expect(partial.hasTrend, isFalse);
    });
  });

  group('PriceTrendCard', () {
    testWidgets('shows the line chart, direction and latest price from backend data', (tester) async {
      final backend = _Backend(_trendJson());
      await _pump(tester, backend, const Scaffold(body: PriceTrendCard(item: 'Laptop', wardId: 'WARD-1')));

      expect(backend.trendQuery, {'item': 'Laptop', 'ward_id': 'WARD-1'});
      expect(find.byKey(const Key('price_trend_chart')), findsOneWidget);
      expect(find.text('Increasing'), findsOneWidget);
      expect(find.text('Trend: Increasing (+4.1%)'), findsOneWidget);
      expect(find.text('Latest market price: ₹510.00/kg (22/09)'), findsOneWidget);
      expect(find.text('Laptop · Ward WARD-1 · Last 90 days'), findsOneWidget);
      expect(find.textContaining('Unavailable'), findsNothing);
    });

    testWidgets('decreasing and stable are shown as the backend reports them', (tester) async {
      await _pump(tester, _Backend(_trendJson(trend: 'decreasing')), const Scaffold(body: PriceTrendCard(item: 'Laptop')));
      expect(find.text('Decreasing'), findsOneWidget);
      await tester.pumpWidget(const SizedBox()); // fresh providers for the next backend
      await _pump(tester, _Backend(_trendJson(trend: 'stable')), const Scaffold(body: PriceTrendCard(item: 'Mouse')));
      expect(find.text('Stable'), findsOneWidget);
    });

    testWidgets('no history: clean empty state, no chart, no direction', (tester) async {
      await _pump(tester, _Backend(_insufficient), const Scaffold(body: PriceTrendCard(item: 'Laptop', wardId: 'WARD-1')));

      expect(find.byKey(const Key('price_trend_insufficient')), findsOneWidget);
      expect(find.text('Not enough historical data yet.'), findsOneWidget);
      expect(find.text('Trend will appear as more market price data is collected.'), findsOneWidget);
      expect(find.byKey(const Key('price_trend_chart')), findsNothing);
      expect(find.text('Increasing'), findsNothing);
      expect(find.text('Decreasing'), findsNothing);
      expect(find.text('Stable'), findsNothing);
    });

    testWidgets('backend failure shows an unavailable message, never a chart', (tester) async {
      await _pump(tester, _Backend(null), const Scaffold(body: PriceTrendCard(item: 'Laptop')));
      expect(find.text('Price trend is unavailable right now.'), findsOneWidget);
      expect(find.byKey(const Key('price_trend_chart')), findsNothing);
    });
  });

  testWidgets('Home User submission detail shows the Price Trend instead of "Trend: Unavailable"', (tester) async {
    final backend = _Backend(_trendJson());
    await _pump(tester, backend, const SubmissionDetailScreen(submissionId: 'sub-1'));

    expect(find.byKey(const Key('price_trend_card')), findsOneWidget);
    expect(backend.trendQuery, {'item': 'Laptop', 'ward_id': 'WARD-1'});
    expect(find.text('Trend: Increasing (+4.1%)'), findsOneWidget);
    expect(find.textContaining('Unavailable'), findsNothing);
  });

  testWidgets('Collector lot detail shows the same Price Trend from the same endpoint', (tester) async {
    final backend = _Backend(_trendJson());
    await _pump(tester, backend, const CollectorLotDetailScreen(lotId: 'lot-00000001'), role: 'COLLECTOR');

    expect(find.byKey(const Key('price_trend_card')), findsOneWidget);
    expect(backend.trendQuery, {'item': 'Laptop', 'ward_id': 'WARD-1'});
    expect(find.text('Latest market price: ₹510.00/kg (22/09)'), findsOneWidget);
    expect(backend.paths.where((p) => p.contains('/pricing/estimate')), isEmpty);
  });
}
