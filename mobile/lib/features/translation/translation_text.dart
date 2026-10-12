import 'package:flutter/widgets.dart';

import 'app_localizations.dart';

/// `context.tr('English text')` returns the text in the app's selected
/// language. Safe in build methods and callbacks alike; outside a localized
/// app (e.g. a bare widget test) it returns the English text.
extension TranslationText on BuildContext {
  String tr(String source) => AppLocalizations.of(this)?.text(source) ?? source;

  /// For nullable messages such as form-validator results.
  String? trOrNull(String? source) => source == null ? null : tr(source);

  /// `context.trf('{count} recyclers have bid', {'count': 3})`.
  String trf(String template, Map<String, Object> args) {
    final localizations = AppLocalizations.of(this);
    if (localizations != null) return localizations.format(template, args);
    var result = template;
    args.forEach((name, value) => result = result.replaceAll('{$name}', '$value'));
    return result;
  }
}
