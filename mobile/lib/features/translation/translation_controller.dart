import 'package:flutter/widgets.dart';

import 'translation_language.dart';
import 'translation_storage.dart';

/// The app's selected UI language (English by default), persisted on the
/// device. MaterialApp's `locale` follows [locale], so a change re-renders
/// every open screen immediately.
class TranslationController extends ChangeNotifier {
  final TranslationStorage storage;

  TranslationController({required this.storage});

  TranslationLanguage language = TranslationLanguage.english;

  String get selectedLanguage => language.code;
  Locale get locale => language.locale;
  bool get isEnglish => language == TranslationLanguage.english;

  Future<void> initialize() async {
    String? saved;
    try {
      saved = await storage.loadLanguage();
    } catch (_) {
      saved = null;
    }
    // No saved choice, or one from a language no longer offered -> English.
    language = TranslationLanguage.byCode(saved) ?? TranslationLanguage.english;
    notifyListeners();
  }

  Future<void> selectLanguage(String code) async {
    final selected = TranslationLanguage.byCode(code);
    if (selected == null || selected == language) return;
    language = selected;
    notifyListeners();
    await storage.saveLanguage(code);
  }
}
