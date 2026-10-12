import 'dart:ui';

class TranslationLanguage {
  /// Stored preference code. Kept identical to the codes earlier app
  /// versions saved, so an existing saved choice keeps working.
  final String code;

  /// Always shown in its own script, so it is recognisable in any language.
  final String nativeName;
  final Locale locale;

  const TranslationLanguage(this.code, this.nativeName, this.locale);

  static const english = TranslationLanguage('eng_Latn', 'English', Locale('en'));
  static const kannada = TranslationLanguage('kan_Knda', 'ಕನ್ನಡ', Locale('kn'));

  static const supported = <TranslationLanguage>[english, kannada];

  static TranslationLanguage? byCode(String? code) {
    for (final language in supported) {
      if (language.code == code) return language;
    }
    return null;
  }
}
