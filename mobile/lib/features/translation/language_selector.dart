import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'translation_controller.dart';
import 'translation_language.dart';
import 'translation_text.dart';

/// The app's one language control: shown on the login / role-selection
/// screen (so it can be chosen before login) and in the Settings screen.
class LanguageSettingTile extends StatelessWidget {
  /// Called after the user picks a different language.
  final ValueChanged<TranslationLanguage>? onChanged;

  const LanguageSettingTile({super.key, this.onChanged});

  @override
  Widget build(BuildContext context) {
    final current = context.watch<TranslationController>().language;
    return ListTile(
      key: const Key('language_setting_tile'),
      leading: const Icon(Icons.translate),
      title: Text(context.tr('App Language')),
      subtitle: Text(current.nativeName),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        final selected = await showLanguagePicker(context);
        if (selected != null && selected != current) onChanged?.call(selected);
      },
    );
  }
}

/// Lets the user choose English or Kannada; the choice is applied and
/// saved immediately. Returns the chosen language, or null if dismissed.
Future<TranslationLanguage?> showLanguagePicker(BuildContext context) {
  final controller = context.read<TranslationController>();
  return showDialog<TranslationLanguage>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text(dialogContext.tr('App Language')),
      contentPadding: const EdgeInsets.symmetric(vertical: 12),
      content: RadioGroup<String>(
        groupValue: controller.selectedLanguage,
        onChanged: (code) async {
          final language = TranslationLanguage.byCode(code);
          if (language == null) return;
          await controller.selectLanguage(language.code);
          if (dialogContext.mounted) Navigator.of(dialogContext).pop(language);
        },
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final language in TranslationLanguage.supported)
              RadioListTile<String>(
                key: Key('language_option_${language.locale.languageCode}'),
                title: Text(language.nativeName),
                value: language.code,
              ),
          ],
        ),
      ),
    ),
  );
}
