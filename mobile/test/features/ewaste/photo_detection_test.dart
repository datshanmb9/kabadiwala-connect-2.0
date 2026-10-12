import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker_platform_interface/image_picker_platform_interface.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/features/auth/auth_controller.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';
import 'package:kabadiwala_mobile/features/ewaste/ewaste_repository.dart';
import 'package:kabadiwala_mobile/features/ewaste/models/submission.dart';
import 'package:kabadiwala_mobile/features/safety/safety_service.dart';
import 'package:kabadiwala_mobile/screens/collector/collector_handover_screen.dart';
import 'package:kabadiwala_mobile/screens/submit_ewaste_screen.dart';
import 'package:provider/provider.dart';

import '../../test_utils/in_memory_auth_storage.dart';

/// A valid 1x1 PNG, so the screens' photo preview can decode it.
final _pngBytes = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
);

/// Stands in for the device camera/gallery.
class _FakeImagePicker extends ImagePickerPlatform {
  @override
  Future<XFile?> getImageFromSource({
    required ImageSource source,
    ImagePickerOptions options = const ImagePickerOptions(),
  }) async =>
      XFile.fromData(Uint8List.fromList(_pngBytes), name: 'item.png', mimeType: 'image/png');
}

/// Shape of the existing POST /api/v1/ai/classify-photo response: YOLO's
/// most confident class in detected_class, the classifier's generic bucket
/// in category (as the real YOLO mapper returns for most classes).
Map<String, dynamic> _detection(String detectedClass, {double confidence = 0.92, int objects = 1}) => {
      'category': confidence >= 0.6 ? 'e-waste-small-appliances' : null,
      'predicted_category': 'e-waste-small-appliances',
      'confidence': confidence,
      'model_version': 'YOLO-best.pt',
      'source': 'AI',
      'needs_review': confidence < 0.6,
      'failure_reason': null,
      'detected_class': detectedClass,
      'bounding_boxes': [
        for (var i = 0; i < objects; i++) [1.0, 2.0, 3.0, 4.0],
      ],
      'object_count': objects,
    };

class _Backend {
  final Map<String, dynamic> detection;
  final paths = <String>[];
  Map<String, dynamic>? estimateBody;
  Map<String, String>? trendQuery;

  _Backend(this.detection);

  late final ApiClient api = ApiClient(
    baseUrl: 'http://test',
    client: MockClient((request) async {
      paths.add(request.url.path);
      switch (request.url.path) {
        case '/api/v1/ewaste/photos':
          return _json({'photo_file_id': 'photo-1'});
        case '/api/v1/ai/classify-photo':
          return _json(detection);
        case '/api/v1/pricing/trend':
          trendQuery = request.url.queryParameters;
          return _json({
            'item': request.url.queryParameters['item'],
            'ward_id': request.url.queryParameters['ward_id'],
            'scope': 'ward',
            'window_days': 90,
            'min_points': 4,
            'points': [],
            'trend': 'insufficient_data',
          });
        case '/api/v1/pricing/estimate':
          estimateBody = jsonDecode(request.body) as Map<String, dynamic>;
          return _json({
            'predicted_price_per_kg': 487.61,
            'min_price': 438.85,
            'max_price': 536.37,
            'estimated_total_value': 195.04,
            'estimated_total_min': 175.54,
            'estimated_total_max': 214.55,
            'product_type': estimateBody!['product_type'],
            'condition': estimateBody!['condition'],
            'weight_kg': estimateBody!['total_weight_kg'],
            'is_estimate': true,
          });
      }
      return _json({});
    }),
  );

  static http.Response _json(Map<String, dynamic> body) =>
      http.Response(jsonEncode(body), 200, headers: {'content-type': 'application/json'});
}

Future<void> _pump(WidgetTester tester, _Backend backend, Widget screen, {required String role}) async {
  final auth = AuthController(repository: AuthRepository(apiClient: backend.api, authStorage: InMemoryAuthStorage()))
    ..session = AuthSession(accessToken: 'tok', refreshToken: 'ref', role: role, userId: 'u-1', username: 'u-1')
    ..status = AuthStatus.authenticated;
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthController>.value(value: auth),
        Provider<EwasteRepository>(create: (_) => EwasteRepository(apiClient: backend.api)),
      ],
      child: MaterialApp(home: screen),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _tapVisible(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

const _pendingSubmission = Submission(
  submissionId: 'sub-12345678',
  homeUserId: 'home-1',
  wardId: 'WARD-1',
  status: 'COLLECTOR_ACCEPTED',
  category: 'Laptop',
);

void main() {
  setUp(() => ImagePickerPlatform.instance = _FakeImagePicker());

  group('detected item name', () {
    test('uses the YOLO class (most confident detection) in readable form', () {
      String? name(String cls) => PhotoClassificationResult.fromJson(_detection(cls)).detectedItemName;
      expect(name('Smartphone'), 'Smartphone');
      expect(name('Laptop'), 'Laptop');
      expect(name('TV-Remote-Control'), 'TV Remote Control');
      expect(name('Computer-Mouse'), 'Computer Mouse');
      expect(PhotoClassificationResult.fromJson({..._detection('x'), 'detected_class': null}).detectedItemName, isNull);
    });

    test('safety guidance follows the detected item', () {
      final safety = SafetyService();
      expect(safety.forCategory('Smartphone').title, 'Smartphone safety');
      expect(safety.forCategory('Laptop').title, 'Laptop safety');
      expect(safety.forCategory('Battery').title, 'Battery safety');
      // "TV Remote Control" contains "tv" but is not a screen device.
      expect(safety.forCategory('TV Remote Control').title, 'Safe e-waste handling');
      expect(safety.forCategory('Flat Panel TV').title, 'TV/CRT safety');
      expect(safety.forCategory('e-waste-small-appliances').title, 'Safe e-waste handling');
    });
  });

  group('Home User submission (existing flow)', () {
    testWidgets('photo is detected; the detected item fills Material and drives safety + pricing', (tester) async {
      final backend = _Backend(_detection('Laptop', objects: 2));
      await _pump(tester, backend, const SubmitEwasteScreen(wardId: 'WARD-1'), role: 'HOME_USER');

      await tester.tap(find.byKey(const Key('pick_photo_camera_button')));
      await tester.pumpAndSettle();

      expect(backend.paths, ['/api/v1/ewaste/photos', '/api/v1/ai/classify-photo']);
      expect(find.text('Detected item: Laptop'), findsOneWidget);
      expect(find.text('Several objects were found; showing the most confident one.'), findsOneWidget);
      final material = tester.widget<TextField>(find.byKey(const Key('submission_category_field')));
      expect(material.controller!.text, 'Laptop');
      expect(find.textContaining('e-waste-small-appliances'), findsNothing);
      expect(find.byKey(const Key('safety_measures_card')), findsOneWidget);
      expect(find.text('Laptop safety'), findsOneWidget);
      expect(find.byKey(const Key('safety_continue_button')), findsOneWidget);

      // Price estimate request carries the same Material value.
      await _tapVisible(tester, find.byKey(const Key('submission_condition_dropdown')));
      await tester.tap(find.text('Used').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('submission_weight_field')), '0.4');
      await _tapVisible(tester, find.byKey(const Key('get_price_estimate_button')));
      expect(backend.estimateBody?['product_type'], 'Laptop');
      // The estimate card now carries the real Price Trend (here: no history yet).
      expect(backend.trendQuery, {'item': 'Laptop', 'ward_id': 'WARD-1'});
      expect(find.byKey(const Key('price_trend_card')), findsOneWidget);
      expect(find.text('Not enough historical data yet.'), findsOneWidget);
      expect(find.textContaining('Unavailable'), findsNothing);
    });

    testWidgets('low-confidence detection leaves Material for manual entry', (tester) async {
      final backend = _Backend(_detection('Smartphone', confidence: 0.3));
      await _pump(tester, backend, const SubmitEwasteScreen(wardId: 'WARD-1'), role: 'HOME_USER');

      await tester.tap(find.byKey(const Key('pick_photo_camera_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('photo_detection_needs_review')), findsOneWidget);
      final material = tester.widget<TextField>(find.byKey(const Key('submission_category_field')));
      expect(material.controller!.text, isEmpty);
    });
  });

  group('Collector handover', () {
    testWidgets('capturing the item photo runs detection and shows the item + safety measures', (tester) async {
      final backend = _Backend(_detection('Smartphone'));
      await _pump(tester, backend, const CollectorHandoverScreen(submission: _pendingSubmission), role: 'COLLECTOR');
      expect(find.byKey(const Key('safety_measures_card')), findsNothing);

      await tester.tap(find.byKey(const Key('handover_pick_photo_camera_button')));
      await tester.pumpAndSettle();

      expect(backend.paths, ['/api/v1/ewaste/photos', '/api/v1/ai/classify-photo']);
      expect(find.text('Detected item: Smartphone'), findsOneWidget);
      expect(find.textContaining('e-waste-small-appliances'), findsNothing);
      expect(find.byKey(const Key('safety_measures_card')), findsOneWidget);
      expect(find.text('Smartphone safety'), findsOneWidget);
      // No extra acknowledgement gate is added to the collector workflow.
      expect(find.byKey(const Key('safety_continue_button')), findsNothing);
    });

    testWidgets('undetected photo falls back to the submission material for safety', (tester) async {
      final backend = _Backend(_detection('Smartphone', confidence: 0.2));
      await _pump(tester, backend, const CollectorHandoverScreen(submission: _pendingSubmission), role: 'COLLECTOR');

      await tester.tap(find.byKey(const Key('handover_pick_photo_camera_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('photo_detection_needs_review')), findsOneWidget);
      expect(find.text('Laptop safety'), findsOneWidget);
    });

    testWidgets('existing handover checks are unchanged: photo gate passes, location still required',
        (tester) async {
      final backend = _Backend(_detection('Laptop'));
      await _pump(tester, backend, const CollectorHandoverScreen(submission: _pendingSubmission), role: 'COLLECTOR');

      await _tapVisible(tester, find.byKey(const Key('confirm_handover_button')));
      expect(find.text('Please capture or select a photo first.'), findsOneWidget);

      await _tapVisible(tester, find.byKey(const Key('handover_pick_photo_camera_button')));
      await _tapVisible(tester, find.byKey(const Key('confirm_handover_button')));
      expect(find.text('Please capture your location first.'), findsOneWidget);
      expect(backend.paths.where((p) => p.endsWith('/handover')), isEmpty);
    });
  });
}
