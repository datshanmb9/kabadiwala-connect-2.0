import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/core/api_exception.dart';
import 'package:kabadiwala_mobile/features/home_user/home_user_repository.dart';

http.Response _json(Map<String, dynamic> body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

void main() {
  group('HomeUserRepository.listWards', () {
    test('parses the ward list without requiring a token', () async {
      String? capturedAuthHeader;
      final repo = HomeUserRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            capturedAuthHeader = req.headers['Authorization'];
            return _json({
              'success': true,
              'wards': [
                {'ward_id': 'WARD-1', 'name': 'Ward One'},
                {'ward_id': 'WARD-2', 'name': 'Ward Two'},
              ],
            }, 200);
          }),
        ),
      );
      final wards = await repo.listWards();
      expect(wards, hasLength(2));
      expect(wards.first.wardId, 'WARD-1');
      expect(capturedAuthHeader, isNull);
    });
  });

  group('HomeUserRepository.register', () {
    test('sends the exact registration request body the backend expects', () async {
      late Map<String, dynamic> capturedBody;
      final repo = HomeUserRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            expect(req.url.path, '/api/v1/home-users/register');
            capturedBody = jsonDecode(req.body) as Map<String, dynamic>;
            return _json({
              'user_id': 'user-1',
              'username': 'citizen1',
              'full_name': 'Citizen One',
              'address': '1 Main St',
              'ward_id': 'WARD-1',
              'household_lat': 12.9716,
              'household_lng': 77.5946,
              'upi_id': null,
            }, 200);
          }),
        ),
      );

      final profile = await repo.register(
        username: 'citizen1',
        password: 'password123',
        fullName: 'Citizen One',
        address: '1 Main St',
        wardId: 'WARD-1',
        householdLat: 12.9716,
        householdLng: 77.5946,
      );

      expect(capturedBody['username'], 'citizen1');
      expect(capturedBody['ward_id'], 'WARD-1');
      expect(capturedBody.containsKey('upi_id'), isFalse, reason: 'omitted when not provided');
      expect(profile.userId, 'user-1');
    });

    test('includes upi_id only when non-empty', () async {
      late Map<String, dynamic> capturedBody;
      final repo = HomeUserRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            capturedBody = jsonDecode(req.body) as Map<String, dynamic>;
            return _json({
              'user_id': 'user-1',
              'username': 'citizen1',
              'full_name': 'Citizen One',
              'address': '1 Main St',
              'ward_id': 'WARD-1',
              'household_lat': 12.9716,
              'household_lng': 77.5946,
              'upi_id': 'citizen1@upi',
            }, 200);
          }),
        ),
      );
      await repo.register(
        username: 'citizen1',
        password: 'password123',
        fullName: 'Citizen One',
        address: '1 Main St',
        wardId: 'WARD-1',
        householdLat: 12.9716,
        householdLng: 77.5946,
        upiId: 'citizen1@upi',
      );
      expect(capturedBody['upi_id'], 'citizen1@upi');
    });

    test('propagates WARD_NOT_FOUND as a structured error', () async {
      final repo = HomeUserRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            return _json({'success': false, 'error_code': 'WARD_NOT_FOUND', 'message': 'No ward exists.'}, 404);
          }),
        ),
      );
      expect(
        () => repo.register(
          username: 'citizen1',
          password: 'password123',
          fullName: 'Citizen One',
          address: '1 Main St',
          wardId: 'NOPE',
          householdLat: 12.9716,
          householdLng: 77.5946,
        ),
        throwsA(isA<ApiException>().having((e) => e.errorCode, 'errorCode', 'WARD_NOT_FOUND')),
      );
    });
  });

  group('HomeUserRepository.getProfile', () {
    test('attaches the bearer token', () async {
      String? capturedAuthHeader;
      final repo = HomeUserRepository(
        apiClient: ApiClient(
          baseUrl: 'http://test',
          client: MockClient((req) async {
            capturedAuthHeader = req.headers['Authorization'];
            return _json({
              'user_id': 'user-1',
              'username': 'citizen1',
              'full_name': 'Citizen One',
              'address': '1 Main St',
              'ward_id': 'WARD-1',
              'household_lat': 12.9716,
              'household_lng': 77.5946,
              'upi_id': null,
            }, 200);
          }),
        ),
      );
      final profile = await repo.getProfile('tok-1');
      expect(capturedAuthHeader, 'Bearer tok-1');
      expect(profile.username, 'citizen1');
    });
  });

  test('updates the authenticated profile without sending a user id', () async {
    late Map<String, dynamic> capturedBody;
    final repo = HomeUserRepository(
      apiClient: ApiClient(
        baseUrl: 'http://test',
        client: MockClient((request) async {
          expect(request.method, 'PATCH');
          expect(request.url.path, '/api/v1/home-users/me');
          expect(request.headers['Authorization'], 'Bearer tok-1');
          capturedBody = jsonDecode(request.body) as Map<String, dynamic>;
          return _json({
            'user_id': 'user-1',
            'username': 'citizen1',
            'full_name': 'Updated',
            'address': 'New address',
            'ward_id': 'WARD-1',
            'household_lat': 12.9716,
            'household_lng': 77.5946,
            'upi_id': null,
          }, 200);
        }),
      ),
    );
    final profile = await repo.updateProfile(
      accessToken: 'tok-1',
      fullName: 'Updated',
      address: 'New address',
    );
    expect(capturedBody, {'full_name': 'Updated', 'address': 'New address'});
    expect(profile.fullName, 'Updated');
  });

  test('persists preference changes through the authenticated endpoint', () async {
    late Map<String, dynamic> capturedBody;
    final repo = HomeUserRepository(
      apiClient: ApiClient(
        baseUrl: 'http://test',
        client: MockClient((request) async {
          expect(request.method, 'PATCH');
          expect(request.url.path, '/api/v1/home-users/me/preferences');
          capturedBody = jsonDecode(request.body) as Map<String, dynamic>;
          return _json({
            'user_id': 'user-1',
            'username': 'citizen1',
            'full_name': 'Citizen One',
            'address': '1 Main St',
            'ward_id': 'WARD-1',
            'household_lat': 12.9716,
            'household_lng': 77.5946,
            'upi_id': null,
            'preferences': {'language': 'hin_Deva', 'status_updates': false},
          }, 200);
        }),
      ),
    );
    final profile = await repo.updatePreferences(
      accessToken: 'tok-1',
      language: 'hin_Deva',
      statusUpdates: false,
    );
    expect(capturedBody, {'language': 'hin_Deva', 'status_updates': false});
    expect(profile.preferences['language'], 'hin_Deva');
    expect(profile.preferences['status_updates'], false);
  });
}
