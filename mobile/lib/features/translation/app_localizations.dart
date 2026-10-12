import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import 'app_strings_kn.dart';

/// App-wide UI strings for the active locale, provided through Flutter's
/// own Localizations mechanism (see [delegate]). English source text is the
/// lookup key, so English needs no table and any text without a Kannada
/// entry (e.g. a server-provided message) is shown unchanged.
class AppLocalizations {
  final Locale locale;
  final Map<String, String> _strings;

  const AppLocalizations(this.locale, this._strings);

  static const supportedLocales = <Locale>[Locale('en'), Locale('kn')];

  static const LocalizationsDelegate<AppLocalizations> delegate = _AppLocalizationsDelegate();

  static AppLocalizations? of(BuildContext context) =>
      Localizations.of<AppLocalizations>(context, AppLocalizations);

  String text(String source) => _strings[source] ?? source;

  /// Translates [template] and then fills its `{name}` placeholders, so
  /// each language can order the words around dynamic values itself.
  String format(String template, Map<String, Object> args) {
    var result = text(template);
    args.forEach((name, value) => result = result.replaceAll('{$name}', '$value'));
    return result;
  }
}

class _AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) =>
      AppLocalizations.supportedLocales.any((l) => l.languageCode == locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) => SynchronousFuture(
        AppLocalizations(locale, locale.languageCode == 'kn' ? kannadaStrings : const {}),
      );

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}
