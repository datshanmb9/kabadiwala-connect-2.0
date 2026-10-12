import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/core/api_exception.dart';
import 'package:kabadiwala_mobile/features/collector/collector_repository.dart';

http.Response _json(Map<String, dynamic> body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

void main() {
  group('CollectorRepository.getProfile', () {
    test('requests the correct path and attaches the bearer token', () async {
      String? capturedAuthHeader;
      String? capturedPath;
      final repo = CollectorRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            capturedAuthHeader = req.headers['Authorization'];
            capturedPath = req.url.path;
            return _json({
              'user_id': 'coll-1',
              'employee_id': 'EMP-001',
              'ward_id': 'WARD-1',
              'rrr_id': null,
              'assigned_area_radius_m': null,
            }, 200);
          }),
        ),
      );
      final profile = await repo.getProfile('tok-1');
      expect(capturedPath, '/api/v1/collectors/me');
      expect(capturedAuthHeader, 'Bearer tok-1');
      expect(profile.employeeId, 'EMP-001');
    });

    test('propagates COLLECTOR_PROFILE_NOT_FOUND as a structured error', () async {
      final repo = CollectorRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({'success': false, 'error_code': 'COLLECTOR_PROFILE_NOT_FOUND', 'message': 'Not found.'}, 404);
          }),
        ),
      );
      expect(
        () => repo.getProfile('tok-1'),
        throwsA(isA<ApiException>().having((e) => e.errorCode, 'errorCode', 'COLLECTOR_PROFILE_NOT_FOUND')),
      );
    });
  });
}
