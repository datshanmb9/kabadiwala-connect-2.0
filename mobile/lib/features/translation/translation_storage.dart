import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract class TranslationKeyValueStore {
  Future<String?> read(String key);

  Future<void> write(String key, String value);

  Future<void> delete(String key);
}

class SecureTranslationKeyValueStore implements TranslationKeyValueStore {
  final FlutterSecureStorage storage;

  SecureTranslationKeyValueStore({FlutterSecureStorage? storage})
      : storage = storage ?? const FlutterSecureStorage();

  @override
  Future<String?> read(String key) => storage.read(key: key);

  @override
  Future<void> write(String key, String value) => storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => storage.delete(key: key);
}

class TranslationStorage {
  // Deliberately NOT the key the earlier machine-translation selector used
  // ('kc_translation_language'): values saved there came from a selector
  // that never actually changed the UI language, so honouring them made the
  // app open in Kannada without a real choice. That old entry is left
  // untouched and ignored; only choices made with the current selector count.
  static const _languageKey = 'kc_app_language';

  final TranslationKeyValueStore _storage;

  TranslationStorage({TranslationKeyValueStore? storage})
      : _storage = storage ?? SecureTranslationKeyValueStore();

  Future<String?> loadLanguage() => _storage.read(_languageKey);

  Future<void> saveLanguage(String code) => _storage.write(_languageKey, code);
}
