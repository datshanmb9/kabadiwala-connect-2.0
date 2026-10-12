import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../features/auth/models/auth_session.dart';

/// Persists the auth session in the platform secure store (Android
/// Keystore-backed / web IndexedDB-backed via flutter_secure_storage).
/// Written and read as a single JSON blob under one key — token and role
/// are never split across separate reads/writes that could drift apart.
class AuthStorage {
  static const _sessionKey = 'kc_auth_session';

  final FlutterSecureStorage _storage;

  AuthStorage({FlutterSecureStorage? storage}) : _storage = storage ?? const FlutterSecureStorage();

  Future<void> saveSession(AuthSession session) async {
    await _storage.write(key: _sessionKey, value: jsonEncode(session.toJson()));
  }

  Future<AuthSession?> loadSession() async {
    final raw = await _storage.read(key: _sessionKey);
    if (raw == null) return null;
    try {
      return AuthSession.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      // Corrupt/old-shape data — treat as no session rather than crashing.
      await clear();
      return null;
    }
  }

  Future<void> clear() async {
    await _storage.delete(key: _sessionKey);
  }
}
