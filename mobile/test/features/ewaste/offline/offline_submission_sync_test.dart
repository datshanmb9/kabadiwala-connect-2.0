import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';
import 'package:kabadiwala_mobile/features/ewaste/ewaste_repository.dart';
import 'package:kabadiwala_mobile/features/ewaste/models/submission.dart';
import 'package:kabadiwala_mobile/features/ewaste/offline/offline_submission_store.dart';
import 'package:kabadiwala_mobile/features/ewaste/offline/offline_submission_sync.dart';

const _session = AuthSession(
  accessToken: 'token-1',
  refreshToken: 'refresh-1',
  role: 'HOME_USER',
  userId: 'user-1',
  username: 'home-user-1',
);

final _photoBytes = Uint8List.fromList(List<int>.generate(64, (i) => i));

const _estimate = PriceEstimate(
  predictedPricePerKg: 109.12,
  minPrice: 98.21,
  maxPrice: 120.03,
  estimatedTotalValue: 43.65,
  estimatedTotalMin: 39.28,
  estimatedTotalMax: 48.01,
  productType: 'e-waste-small-appliances',
  condition: 'Used',
  weightKg: 0.40,
  isEstimate: true,
);

/// Minimal stand-in for the backend: photo upload + submission create with
/// the real server's idempotency semantics (same key -> same submission).
class FakeBackend {
  bool online = true;
  bool dropCreateResponse = false; // server commits, but the reply is lost
  String validToken = 'token-1';
  int photoUploads = 0;
  int createCalls = 0;
  final submissionsByKey = <String, Map<String, dynamic>>{};
  final uploadedPhotoBytes = <List<int>>[];
  final createBodies = <Map<String, dynamic>>[];
  final createKeys = <String>[];

  late final ApiClient apiClient = ApiClient(baseUrl: 'http://test', client: MockClient.streaming(_handle));

  http.StreamedResponse _json(Map<String, dynamic> body, [int status = 200]) =>
      http.StreamedResponse(Stream.value(utf8.encode(jsonEncode(body))), status,
          headers: {'content-type': 'application/json'});

  Future<http.StreamedResponse> _handle(http.BaseRequest request, http.ByteStream bodyStream) async {
    final body = await bodyStream.toBytes();
    if (!online) throw http.ClientException('offline');
    if (request.headers['Authorization'] != 'Bearer $validToken') {
      return _json({'success': false, 'error_code': 'INVALID_TOKEN', 'message': 'expired'}, 401);
    }
    if (request.url.path == '/api/v1/ewaste/photos') {
      photoUploads++;
      uploadedPhotoBytes.add(body);
      return _json({'photo_file_id': 'photo-$photoUploads'});
    }
    if (request.url.path == '/api/v1/ewaste/submissions') {
      createCalls++;
      final key = request.headers['Idempotency-Key']!;
      createKeys.add(key);
      createBodies.add(jsonDecode(utf8.decode(body)) as Map<String, dynamic>);
      final response = submissionsByKey.putIfAbsent(
        key,
        () => {'submission_id': 'sub-${submissionsByKey.length + 1}', 'status': 'WAITING_FOR_COLLECTION'},
      );
      if (dropCreateResponse) throw http.ClientException('connection lost mid-request');
      return _json(response);
    }
    return _json({'success': false, 'error_code': 'NOT_FOUND', 'message': 'no route'}, 404);
  }
}

bool _containsBytes(List<int> haystack, List<int> needle) {
  for (var i = 0; i + needle.length <= haystack.length; i++) {
    var match = true;
    for (var j = 0; j < needle.length && match; j++) {
      match = haystack[i + j] == needle[j];
    }
    if (match) return true;
  }
  return false;
}

void main() {
  late Directory tempDir;
  late FakeBackend backend;
  late OfflineSubmissionStore store;
  late List<SubmissionCreateResult> synced;
  late StreamController<List<ConnectivityResult>> connectivity;
  AuthSession? session;

  OfflineSubmissionSync buildSync({Future<String?> Function()? refresh}) => OfflineSubmissionSync(
        store: store,
        repository: EwasteRepository(apiClient: backend.apiClient),
        currentSession: () => session,
        refreshAccessToken: refresh ?? () async => null,
        onSynced: synced.add,
        connectivityChanges: () => connectivity.stream,
      );

  Future<void> enqueue(OfflineSubmissionSync sync, {String key = 'idem-1', String userId = 'user-1'}) =>
      sync.enqueue(
        userId: userId,
        idempotencyKey: key,
        wardId: 'WARD-1',
        homeLat: 12.9716,
        homeLng: 77.5946,
        category: 'e-waste-small-appliances',
        condition: 'Used',
        approximateWeightKg: 0.40,
        priceEstimate: _estimate,
        photoBytes: _photoBytes,
        photoName: 'image_picker_123.jpg',
      );

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('offline_sync_test');
    backend = FakeBackend();
    store = OfflineSubmissionStore(baseDirectory: () async => tempDir);
    synced = [];
    connectivity = StreamController<List<ConnectivityResult>>.broadcast();
    session = _session;
  });

  tearDown(() async {
    await connectivity.close();
    if (await tempDir.exists()) await tempDir.delete(recursive: true);
  });

  group('offline queue storage', () {
    test('persists the complete submission and survives an app restart', () async {
      await enqueue(buildSync());

      // A brand-new store instance = the app was restarted.
      final restarted = OfflineSubmissionStore(baseDirectory: () async => tempDir);
      final queued = await restarted.list();
      expect(queued, hasLength(1));
      final item = queued.single;
      expect(item.userId, 'user-1');
      expect(item.idempotencyKey, 'idem-1');
      expect(item.wardId, 'WARD-1');
      expect(item.homeLat, 12.9716);
      expect(item.category, 'e-waste-small-appliances');
      expect(item.condition, 'Used');
      expect(item.approximateWeightKg, 0.40);
      expect(item.priceEstimate?['min_price'], 98.21);
      expect(item.photoFileId, isNull);
    });

    test('photo is copied into app storage, independent of the picker temp file', () async {
      final pickerTemp = File('${tempDir.path}${Platform.pathSeparator}picker_tmp.jpg');
      await pickerTemp.writeAsBytes(_photoBytes);
      final sync = buildSync();
      await sync.enqueue(
        userId: 'user-1',
        idempotencyKey: 'idem-1',
        wardId: 'WARD-1',
        homeLat: 1,
        homeLng: 1,
        photoBytes: await pickerTemp.readAsBytes(),
        photoName: 'picker_tmp.png',
      );
      await pickerTemp.delete(); // the OS cleared the picker's temp file

      final item = (await store.list()).single;
      expect(item.photoFileName, 'photo.png');
      final persisted = await store.photoFile(item);
      expect(persisted.path, isNot(pickerTemp.path));
      expect(await persisted.readAsBytes(), _photoBytes);
    });
  });

  group('synchronization', () {
    test('sends the queued submission through the normal flow, then removes it and notifies', () async {
      final sync = buildSync();
      await enqueue(sync);

      await sync.syncPending();

      expect(backend.photoUploads, 1);
      // Multipart body carries the persisted photo's exact bytes.
      expect(_containsBytes(backend.uploadedPhotoBytes.single, _photoBytes), isTrue);
      expect(backend.createKeys, ['idem-1']);
      final body = backend.createBodies.single;
      expect(body['ward_id'], 'WARD-1');
      expect(body['photo_file_id'], 'photo-1');
      expect(body['category'], 'e-waste-small-appliances');
      expect(body['condition'], 'Used');
      expect(body['approximate_weight_kg'], 0.40);
      expect(body['price_estimate']['estimated_total_max'], 48.01);
      expect(await store.list(), isEmpty);
      expect(synced.single.submissionId, 'sub-1');
      expect(offlineSyncedMessage, 'Your e-waste submission has been sent to the collector.');
    });

    test('connectivity restored triggers sync automatically; "none" does not', () async {
      final sync = buildSync()..start();
      await enqueue(sync);

      connectivity.add([ConnectivityResult.none]);
      await pumpEventQueue();
      expect(backend.createCalls, 0);

      connectivity.add([ConnectivityResult.wifi]);
      await pumpEventQueue();
      await sync.syncPending();
      expect(backend.createCalls, 1);
      expect(await store.list(), isEmpty);
      sync.dispose();
    });

    test('stays queued while offline and retries later without re-uploading the photo', () async {
      final sync = buildSync();
      await enqueue(sync);
      backend.online = false;

      await sync.syncPending();
      expect(await store.list(), hasLength(1));
      expect(synced, isEmpty);
      expect((await store.list()).single.lastError, 'NETWORK_ERROR');

      // Photo upload succeeds, then the connection drops before create.
      backend.online = true;
      backend.dropCreateResponse = true;
      await sync.syncPending();
      final stillQueued = (await store.list()).single;
      expect(stillQueued.photoFileId, 'photo-1');
      expect(synced, isEmpty);

      backend.dropCreateResponse = false;
      await sync.syncPending();
      expect(backend.photoUploads, 1);
      expect(await store.list(), isEmpty);
      expect(synced.single.submissionId, 'sub-1');
    });
  });

  group('duplicate prevention', () {
    test('retries always replay the same idempotency key -> exactly one backend submission', () async {
      final sync = buildSync();
      await enqueue(sync);
      backend.dropCreateResponse = true; // server saved it, phone never heard back
      await sync.syncPending();
      await sync.syncPending();
      backend.dropCreateResponse = false;
      await sync.syncPending();

      expect(backend.createKeys.toSet(), {'idem-1'});
      expect(backend.submissionsByKey, hasLength(1));
      expect(synced, hasLength(1));
      expect(await store.list(), isEmpty);
    });

    test('overlapping triggers run a single sync pass', () async {
      final sync = buildSync();
      await enqueue(sync);

      await Future.wait([sync.syncPending(), sync.syncPending(), sync.syncPending()]);

      expect(backend.createCalls, 1);
      expect(backend.photoUploads, 1);
      expect(synced, hasLength(1));
    });

    test('after restart the queued item is sent once, with its original key', () async {
      await enqueue(buildSync(), key: 'idem-restart');

      final afterRestart = OfflineSubmissionSync(
        store: OfflineSubmissionStore(baseDirectory: () async => tempDir),
        repository: EwasteRepository(apiClient: backend.apiClient),
        currentSession: () => session,
        refreshAccessToken: () async => null,
        onSynced: synced.add,
      );
      await afterRestart.syncPending();
      await afterRestart.syncPending();

      expect(backend.createKeys, ['idem-restart']);
    });
  });

  group('session handling', () {
    test('expired access token is refreshed once and the sync continues', () async {
      backend.validToken = 'token-2';
      final sync = buildSync(refresh: () async => 'token-2');
      await enqueue(sync);

      await sync.syncPending();

      expect(synced, hasLength(1));
      expect(await store.list(), isEmpty);
    });

    test('refresh refused -> item stays queued (never lost)', () async {
      backend.validToken = 'token-2';
      final sync = buildSync();
      await enqueue(sync);

      await sync.syncPending();

      expect((await store.list()).single.lastError, 'INVALID_TOKEN');
      expect(synced, isEmpty);
    });

    test('only the logged-in home user\'s queued items are sent', () async {
      final sync = buildSync();
      await enqueue(sync, userId: 'someone-else');

      await sync.syncPending();
      session = null;
      await sync.syncPending();

      expect(backend.createCalls, 0);
      expect(await store.list(), hasLength(1));
    });
  });
}
