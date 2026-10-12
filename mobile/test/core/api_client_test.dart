import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/core/api_exception.dart';

void main() {
  group('ApiClient success path', () {
    test('GET decodes a successful JSON body', () async {
      final client = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          return http.Response(jsonEncode({'success': true, 'value': 42}), 200);
        }),
      );
      final result = await client.get('/x');
      expect(result['value'], 42);
    });

    test('POST attaches Authorization and Idempotency-Key headers', () async {
      late Map<String, String> capturedHeaders;
      late String capturedBody;
      final client = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          capturedHeaders = req.headers;
          capturedBody = req.body;
          return http.Response(jsonEncode({'success': true}), 200);
        }),
      );
      await client.post(
        '/x',
        token: 'tok-1',
        idempotencyKey: 'idem-1',
        body: {'a': 1},
      );
      expect(capturedHeaders['Authorization'], 'Bearer tok-1');
      expect(capturedHeaders['Idempotency-Key'], 'idem-1');
      expect(jsonDecode(capturedBody), {'a': 1});
    });

    test('POST omits Authorization header when no token given', () async {
      late Map<String, String> capturedHeaders;
      final client = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          capturedHeaders = req.headers;
          return http.Response(jsonEncode({'success': true}), 200);
        }),
      );
      await client.post('/x', body: {'a': 1});
      expect(capturedHeaders.containsKey('Authorization'), isFalse);
    });
  });

  group('ApiClient structured backend errors', () {
    test('propagates {success:false,error_code,message} as ApiException', () async {
      final client = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          return http.Response(
            jsonEncode({'success': false, 'error_code': 'INVALID_CREDENTIALS', 'message': 'Invalid username or password.'}),
            401,
          );
        }),
      );
      expect(
        () => client.post('/api/v1/auth/login', body: {}),
        throwsA(
          isA<ApiException>()
              .having((e) => e.errorCode, 'errorCode', 'INVALID_CREDENTIALS')
              .having((e) => e.statusCode, 'statusCode', 401),
        ),
      );
    });

    test('isInvalidToken is true only for INVALID_TOKEN', () async {
      final client = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          return http.Response(jsonEncode({'success': false, 'error_code': 'INVALID_TOKEN', 'message': 'Invalid.'}), 401);
        }),
      );
      try {
        await client.get('/x');
        fail('should have thrown');
      } on ApiException catch (e) {
        expect(e.isInvalidToken, isTrue);
      }
    });
  });

  group('ApiClient non-contract error shapes', () {
    test('FastAPI 422 validation errors become a structured VALIDATION_ERROR', () async {
      final client = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          return http.Response(
            jsonEncode({
              'detail': [
                {'loc': ['body', 'password'], 'msg': 'field required', 'type': 'value_error.missing'}
              ]
            }),
            422,
          );
        }),
      );
      expect(
        () => client.post('/x', body: {}),
        throwsA(isA<ApiException>().having((e) => e.errorCode, 'errorCode', 'VALIDATION_ERROR')),
      );
    });

    test('a non-JSON 500 body still becomes a structured ApiException, not a crash', () async {
      final client = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          return http.Response('Internal Server Error', 500);
        }),
      );
      expect(
        () => client.get('/x'),
        throwsA(isA<ApiException>().having((e) => e.errorCode, 'errorCode', 'UNKNOWN_ERROR')),
      );
    });
  });

  group('ApiClient network failures', () {
    test('a SocketException becomes NETWORK_ERROR', () async {
      final client = ApiClient(
        baseUrl: 'http://test',
        client: MockClient((req) async {
          throw const SocketException('connection refused');
        }),
      );
      expect(
        () => client.get('/x'),
        throwsA(isA<ApiException>().having((e) => e.errorCode, 'errorCode', 'NETWORK_ERROR')),
      );
    });

    test('a request slower than the configured timeout becomes NETWORK_TIMEOUT', () async {
      final client = ApiClient(
        baseUrl: 'http://test',
        timeout: const Duration(milliseconds: 100),
        client: MockClient((req) async {
          await Future.delayed(const Duration(seconds: 2));
          return http.Response('{}', 200);
        }),
      );
      expect(
        () => client.get('/x'),
        throwsA(isA<ApiException>().having((e) => e.errorCode, 'errorCode', 'NETWORK_TIMEOUT')),
      );
    });
  });
}
