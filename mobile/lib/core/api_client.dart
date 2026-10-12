import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import 'api_exception.dart';
import 'config.dart';

/// Centralized HTTP layer — every API call in the app goes through this,
/// nothing constructs its own http.Client or parses a response body
/// directly. Accepts an injected [http.Client] so tests can substitute
/// `http.testing.MockClient` without touching the network.
class ApiClient {
  final http.Client _client;
  final String baseUrl;
  final Duration timeout;

  ApiClient({http.Client? client, String? baseUrl, Duration? timeout})
      : _client = client ?? http.Client(),
        baseUrl = baseUrl ?? AppConfig.apiBaseUrl,
        timeout = timeout ?? AppConfig.requestTimeout;

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  Map<String, String> _headers({String? token, String? idempotencyKey}) {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (token != null) headers['Authorization'] = 'Bearer $token';
    if (idempotencyKey != null) headers['Idempotency-Key'] = idempotencyKey;
    return headers;
  }

  Future<Map<String, dynamic>> get(String path, {String? token}) async {
    final response = await _send(
      () => _client.get(_uri(path), headers: _headers(token: token)),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? body,
    String? token,
    String? idempotencyKey,
  }) async {
    final response = await _send(
      () => _client.post(
        _uri(path),
        headers: _headers(token: token, idempotencyKey: idempotencyKey),
        body: body == null ? null : jsonEncode(body),
      ),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> patch(
    String path, {
    Map<String, dynamic>? body,
    String? token,
  }) async {
    final response = await _send(
      () => _client.patch(
        _uri(path),
        headers: _headers(token: token),
        body: body == null ? null : jsonEncode(body),
      ),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required http.MultipartFile file,
    String? token,
    Map<String, String> fields = const {},
  }) async {
    final request = http.MultipartRequest('POST', _uri(path));
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    request.fields.addAll(fields);
    request.files.add(file);
    final response = await _send(() async {
      final streamed = await _client.send(request);
      return http.Response.fromStream(streamed);
    });
    return _decode(response);
  }

  Future<http.Response> _send(Future<http.Response> Function() call) async {
    try {
      return await call().timeout(timeout);
    } on TimeoutException {
      throw const ApiException(
        errorCode: 'NETWORK_TIMEOUT',
        message: 'The server took too long to respond. Please try again.',
      );
    } on SocketException {
      throw const ApiException(
        errorCode: 'NETWORK_ERROR',
        message: 'Could not reach the server. Check your connection and try again.',
      );
    } on http.ClientException {
      throw const ApiException(
        errorCode: 'NETWORK_ERROR',
        message: 'Could not reach the server. Check your connection and try again.',
      );
    }
  }

  Map<String, dynamic> _decode(http.Response response) {
    Map<String, dynamic>? body;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) body = decoded;
    } catch (_) {
      // Non-JSON body — handled below via the status-code fallback.
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return body ?? <String, dynamic>{};
    }

    // The app's own structured error contract:
    // {"success": false, "error_code": "...", "message": "..."}
    if (body != null && body['error_code'] is String && body['message'] is String) {
      throw ApiException(
        errorCode: body['error_code'] as String,
        message: body['message'] as String,
        statusCode: response.statusCode,
      );
    }

    // FastAPI's own validation-error shape (422) doesn't match the app
    // contract — surface it as a distinct, still-structured error rather
    // than crashing on a missing field.
    if (response.statusCode == 422 && body != null && body['detail'] != null) {
      throw ApiException(
        errorCode: 'VALIDATION_ERROR',
        message: 'The request was invalid. Please check the form and try again.',
        statusCode: response.statusCode,
      );
    }

    throw ApiException(
      errorCode: 'UNKNOWN_ERROR',
      message: 'Something went wrong (HTTP ${response.statusCode}).',
      statusCode: response.statusCode,
    );
  }
}
