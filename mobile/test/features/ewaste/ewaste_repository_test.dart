import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker/image_picker.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/core/api_exception.dart';
import 'package:kabadiwala_mobile/features/ewaste/ewaste_repository.dart';

http.Response _json(Map<String, dynamic> body, int status) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json'},
);

void main() {
  test('uploadPhoto sends the captured image as multipart data', () async {
    final tempDirectory = await Directory.systemTemp.createTemp('kabadiwala-upload-test');
    final imageFile = File('${tempDirectory.path}/photo.jpg');
    await imageFile.writeAsBytes([1, 2, 3]);

    final repo = EwasteRepository(
      apiClient: ApiClient(
        baseUrl: 'http://test',
        client: MockClient((request) async {
          final serialized = request;
          expect(request.url.path, '/api/v1/ewaste/photos');
          expect(request.headers['Authorization'], 'Bearer tok-1');
          expect(request.headers['content-type'], startsWith('multipart/form-data;'));
          expect(serialized.body, contains('photo.jpg'));
          return _json({'photo_file_id': 'uploaded-photo:abc.jpg'}, 200);
        }),
      ),
    );

    final photoFileId = await repo.uploadPhoto(
      accessToken: 'tok-1',
      file: XFile(imageFile.path),
    );

    expect(photoFileId, 'uploaded-photo:abc.jpg');
    await tempDirectory.delete(recursive: true);
  });

  group('EwasteRepository.createSubmission', () {
    test(
      'sends the exact request shape the backend expects, with Idempotency-Key',
      () async {
        late Map<String, String> capturedHeaders;
        late Map<String, dynamic> capturedBody;
        final repo = EwasteRepository(
          apiClient: ApiClient(
            baseUrl: 'http://test',
            client: MockClient((req) async {
              expect(req.url.path, '/api/v1/ewaste/submissions');
              capturedHeaders = req.headers;
              capturedBody = jsonDecode(req.body) as Map<String, dynamic>;
              return _json({
                'submission_id': 'sub-1',
                'status': 'WAITING_FOR_COLLECTION',
              }, 200);
            }),
          ),
        );

        final result = await repo.createSubmission(
          accessToken: 'tok-1',
          wardId: 'WARD-1',
          photoFileId: 'local-photo:abc',
          homeLat: 12.9716,
          homeLng: 77.5946,
          category: 'cables',
          approximateWeightKg: 1.5,
          idempotencyKey: 'idem-1',
        );

        expect(capturedHeaders['Authorization'], 'Bearer tok-1');
        expect(capturedHeaders['Idempotency-Key'], 'idem-1');
        expect(capturedBody['ward_id'], 'WARD-1');
        expect(capturedBody['photo_file_id'], 'local-photo:abc');
        expect(capturedBody['home_lat'], 12.9716);
        expect(capturedBody['home_lng'], 77.5946);
        expect(capturedBody['category'], 'cables');
        expect(capturedBody['approximate_weight_kg'], 1.5);
        expect(result.submissionId, 'sub-1');
        expect(result.status, 'WAITING_FOR_COLLECTION');
      },
    );

    test(
      'a retry with the SAME idempotency key sends the same key value again',
      () async {
        final sentKeys = <String?>[];
        final repo = EwasteRepository(
          apiClient: ApiClient(
            baseUrl: 'http://test',
            client: MockClient((req) async {
              sentKeys.add(req.headers['Idempotency-Key']);
              return _json({
                'submission_id': 'sub-1',
                'status': 'WAITING_FOR_COLLECTION',
              }, 200);
            }),
          ),
        );
        const key = 'fixed-retry-key';
        await repo.createSubmission(
          accessToken: 'tok-1',
          wardId: 'WARD-1',
          photoFileId: 'p',
          homeLat: 1,
          homeLng: 1,
          idempotencyKey: key,
        );
        await repo.createSubmission(
          accessToken: 'tok-1',
          wardId: 'WARD-1',
          photoFileId: 'p',
          homeLat: 1,
          homeLng: 1,
          idempotencyKey: key,
        );
        expect(sentKeys, [key, key]);
      },
    );

    test('propagates WARD_NOT_FOUND as a structured error', () async {
      final repo = EwasteRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({
              'success': false,
              'error_code': 'WARD_NOT_FOUND',
              'message': 'No ward exists.',
            }, 404);
          }),
        ),
      );
      expect(
        () => repo.createSubmission(
          accessToken: 'tok-1',
          wardId: 'NOPE',
          photoFileId: 'p',
          homeLat: 1,
          homeLng: 1,
          idempotencyKey: 'k',
        ),
        throwsA(
          isA<ApiException>().having(
            (e) => e.errorCode,
            'errorCode',
            'WARD_NOT_FOUND',
          ),
        ),
      );
    });
  });

  group('EwasteRepository.listSubmissions', () {
    test('parses the submissions list and attaches the bearer token', () async {
      String? capturedAuthHeader;
      final repo = EwasteRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            capturedAuthHeader = req.headers['Authorization'];
            return _json({
              'success': true,
              'submissions': [
                {
                  'submission_id': 'sub-1',
                  'home_user_id': 'user-1',
                  'ward_id': 'WARD-1',
                  'status': 'WAITING_FOR_COLLECTION',
                  'home_lat': 1.0,
                  'home_lng': 1.0,
                  'home_ts': '2026-01-10T12:00:00',
                },
              ],
            }, 200);
          }),
        ),
      );
      final submissions = await repo.listSubmissions('tok-1');
      expect(submissions, hasLength(1));
      expect(submissions.first.status, 'WAITING_FOR_COLLECTION');
      expect(capturedAuthHeader, 'Bearer tok-1');
    });
  });

  group('EwasteRepository.getSubmission', () {
    test('requests the correct path and parses the detail response', () async {
      final repo = EwasteRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            expect(req.url.path, '/api/v1/ewaste/submissions/sub-1');
            return _json({
              'submission_id': 'sub-1',
              'home_user_id': 'user-1',
              'ward_id': 'WARD-1',
              'status': 'COLLECTED',
              'home_lat': 1.0,
              'home_lng': 1.0,
              'home_ts': '2026-01-10T12:00:00',
            }, 200);
          }),
        ),
      );
      final submission = await repo.getSubmission('sub-1', 'tok-1');
      expect(submission.status, 'COLLECTED');
    });

    test('propagates NOT_RESOURCE_OWNER as a structured error', () async {
      final repo = EwasteRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({
              'success': false,
              'error_code': 'NOT_RESOURCE_OWNER',
              'message': 'No access.',
            }, 403);
          }),
        ),
      );
      expect(
        () => repo.getSubmission('sub-1', 'tok-1'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.errorCode,
            'errorCode',
            'NOT_RESOURCE_OWNER',
          ),
        ),
      );
    });
  });

  group('EwasteRepository.listPendingForCollector (Phase 4)', () {
    test(
      'requests the pending-queue path and attaches the bearer token',
      () async {
        String? capturedPath;
        String? capturedAuthHeader;
        final repo = EwasteRepository(
          apiClient: ApiClient(
            baseUrl: 'http://test',
            client: MockClient((req) async {
              capturedPath = req.url.path;
              capturedAuthHeader = req.headers['Authorization'];
              return _json({
                'success': true,
                'submissions': [
                  {
                    'submission_id': 'sub-1',
                    'home_user_id': 'user-1',
                    'ward_id': 'WARD-1',
                    'status': 'WAITING_FOR_COLLECTION',
                    'home_lat': 1.0,
                    'home_lng': 1.0,
                    'home_ts': '2026-01-10T12:00:00',
                  },
                ],
              }, 200);
            }),
          ),
        );
        final submissions = await repo.listPendingForCollector('tok-1');
        expect(capturedPath, '/api/v1/ewaste/submissions/pending');
        expect(capturedAuthHeader, 'Bearer tok-1');
        expect(submissions, hasLength(1));
      },
    );

    test('propagates FORBIDDEN_ROLE as a structured error', () async {
      final repo = EwasteRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({
              'success': false,
              'error_code': 'FORBIDDEN_ROLE',
              'message': 'No access.',
            }, 403);
          }),
        ),
      );
      expect(
        () => repo.listPendingForCollector('tok-1'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.errorCode,
            'errorCode',
            'FORBIDDEN_ROLE',
          ),
        ),
      );
    });
  });

  group('EwasteRepository.collector acceptance', () {
    test('accepts a submission with an idempotency key', () async {
      late String capturedPath;
      late String? capturedKey;
      final repo = EwasteRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            capturedPath = req.url.path;
            capturedKey = req.headers['Idempotency-Key'];
            return _json({
              'submission_id': 'sub-1',
              'status': 'COLLECTOR_ACCEPTED',
              'assigned_collector_id': 'collector-1',
            }, 200);
          }),
        ),
      );
      final result = await repo.acceptSubmission(
        accessToken: 'tok-1',
        submissionId: 'sub-1',
        idempotencyKey: 'accept-1',
      );
      expect(capturedPath, '/api/v1/ewaste/submissions/sub-1/accept');
      expect(capturedKey, 'accept-1');
      expect(result.status, 'COLLECTOR_ACCEPTED');
      expect(result.assignedCollectorId, 'collector-1');
    });

    test('requests the assigned queue path', () async {
      final repo = EwasteRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            expect(req.url.path, '/api/v1/ewaste/submissions/assigned');
            return _json({'success': true, 'submissions': []}, 200);
          }),
        ),
      );
      expect(await repo.listAssignedForCollector('tok-1'), isEmpty);
    });
  });

  group('EwasteRepository.handover (Phase 4)', () {
    test(
      'sends the exact request shape the backend expects, with Idempotency-Key',
      () async {
        late Map<String, String> capturedHeaders;
        late Map<String, dynamic> capturedBody;
        String? capturedPath;
        final repo = EwasteRepository(
          apiClient: ApiClient(
            baseUrl: 'http://test',
            client: MockClient((req) async {
              capturedPath = req.url.path;
              capturedHeaders = req.headers;
              capturedBody = jsonDecode(req.body) as Map<String, dynamic>;
              return _json({
                'submission_id': 'sub-1',
                'status': 'COLLECTED',
                'verification_result': 'VERIFIED',
                'distance_m': 12.5,
                'reasons': [],
              }, 200);
            }),
          ),
        );

        final result = await repo.handover(
          accessToken: 'tok-1',
          submissionId: 'sub-1',
          photoFileId: 'local-photo:abc',
          collectorLat: 12.9716,
          collectorLng: 77.5946,
          actualWeightKg: 2.25,
          idempotencyKey: 'idem-1',
        );

        expect(capturedPath, '/api/v1/ewaste/submissions/sub-1/handover');
        expect(capturedHeaders['Authorization'], 'Bearer tok-1');
        expect(capturedHeaders['Idempotency-Key'], 'idem-1');
        expect(capturedBody['photo_file_id'], 'local-photo:abc');
        expect(capturedBody['collector_lat'], 12.9716);
        expect(capturedBody['collector_lng'], 77.5946);
        expect(capturedBody['actual_weight_kg'], 2.25);
        expect(result.isVerified, isTrue);
        expect(result.status, 'COLLECTED');
      },
    );

    test(
      'a retry with the SAME idempotency key sends the same key value again',
      () async {
        final sentKeys = <String?>[];
        final repo = EwasteRepository(
          apiClient: ApiClient(
            baseUrl: 'http://test',
            client: MockClient((req) async {
              sentKeys.add(req.headers['Idempotency-Key']);
              return _json({
                'submission_id': 'sub-1',
                'status': 'COLLECTED',
                'verification_result': 'VERIFIED',
                'distance_m': 1.0,
                'reasons': [],
              }, 200);
            }),
          ),
        );
        const key = 'fixed-handover-retry-key';
        await repo.handover(
          accessToken: 'tok-1',
          submissionId: 'sub-1',
          photoFileId: 'p',
          collectorLat: 1,
          collectorLng: 1,
          idempotencyKey: key,
        );
        await repo.handover(
          accessToken: 'tok-1',
          submissionId: 'sub-1',
          photoFileId: 'p',
          collectorLat: 1,
          collectorLng: 1,
          idempotencyKey: key,
        );
        expect(sentKeys, [key, key]);
      },
    );

    test(
      'propagates COLLECTOR_OUTSIDE_ASSIGNED_AREA as a structured error',
      () async {
        final repo = EwasteRepository(
          apiClient: ApiClient(
            baseUrl: 'http://test',
            client: MockClient((req) async {
              return _json({
                'success': false,
                'error_code': 'COLLECTOR_OUTSIDE_ASSIGNED_AREA',
                'message': 'Outside ward.',
              }, 403);
            }),
          ),
        );
        expect(
          () => repo.handover(
            accessToken: 'tok-1',
            submissionId: 'sub-1',
            photoFileId: 'p',
            collectorLat: 1,
            collectorLng: 1,
            idempotencyKey: 'k',
          ),
          throwsA(
            isA<ApiException>().having(
              (e) => e.errorCode,
              'errorCode',
              'COLLECTOR_OUTSIDE_ASSIGNED_AREA',
            ),
          ),
        );
      },
    );
  });
}
