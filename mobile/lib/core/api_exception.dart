/// Mirrors the backend's structured error contract exactly:
/// `{"success": false, "error_code": "...", "message": "..."}`
/// (see backend/app/core/errors.py). Every failure path in the app — HTTP
/// error responses, network failures, timeouts, unparseable bodies — ends
/// up as one of these, never a raw/opaque exception surfaced to the UI.
class ApiException implements Exception {
  final String errorCode;
  final String message;
  final int? statusCode;

  const ApiException({
    required this.errorCode,
    required this.message,
    this.statusCode,
  });

  /// True for the specific case the auth layer needs to react to: an
  /// access token that's missing/expired/invalid, worth trying a refresh
  /// before giving up.
  bool get isInvalidToken => errorCode == 'INVALID_TOKEN';

  @override
  String toString() => 'ApiException($errorCode, $message, status=$statusCode)';
}
