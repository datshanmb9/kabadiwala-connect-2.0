import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../core/location_service.dart';
import '../features/auth/auth_controller.dart';
import '../features/home_user/home_user_repository.dart';
import '../features/home_user/models/home_user_profile.dart';
import '../features/translation/language_selector.dart';
import '../features/translation/translation_language.dart';
import '../features/translation/translation_text.dart';

class UserSettingsScreen extends StatefulWidget {
  const UserSettingsScreen({super.key});

  @override
  State<UserSettingsScreen> createState() => _UserSettingsScreenState();
}

class _UserSettingsScreenState extends State<UserSettingsScreen> {
  final _locationService = LocationService();
  HomeUserProfile? _profile;
  LocationPermission? _permission;
  bool? _locationEnabled;
  bool _loading = true;
  bool _savingPreference = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      final results = await Future.wait([
        context.read<HomeUserRepository>().getProfile(token),
        _locationService.checkPermission(),
        _locationService.isServiceEnabled(),
      ]);
      if (!mounted) return;
      setState(() {
        _profile = results[0] as HomeUserProfile;
        _permission = results[1] as LocationPermission;
        _locationEnabled = results[2] as bool;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.tr('Unable to load your profile.');
        _loading = false;
      });
    }
  }

  bool _preference(String key, {bool fallback = true}) {
    final value = _profile?.preferences[key];
    return value is bool ? value : fallback;
  }

  /// The language itself is applied and stored on the device by the shared
  /// picker; this only mirrors the choice to the home user's profile
  /// preferences, as this screen already did.
  Future<void> _saveLanguagePreference(TranslationLanguage language) async {
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      final updated = await context.read<HomeUserRepository>().updatePreferences(
        accessToken: token,
        language: language.code,
      );
      if (mounted) setState(() => _profile = updated);
    } on ApiException catch (e) {
      if (mounted) _showError(e.message);
    } catch (_) {
      if (mounted) _showError(context.tr('Could not save this preference.'));
    }
  }

  Future<void> _updatePreference(String key, bool value) async {
    if (_savingPreference) return;
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    setState(() => _savingPreference = true);
    try {
      final updated = await context.read<HomeUserRepository>().updatePreferences(
        accessToken: token,
        collectionUpdates: key == 'collection_updates' ? value : null,
        statusUpdates: key == 'status_updates' ? value : null,
        accountUpdates: key == 'account_updates' ? value : null,
      );
      if (mounted) setState(() => _profile = updated);
    } on ApiException catch (e) {
      if (mounted) _showError(e.message);
    } catch (_) {
      if (mounted) _showError(context.tr('Could not save this preference.'));
    } finally {
      if (mounted) setState(() => _savingPreference = false);
    }
  }

  Future<void> _requestLocation() async {
    try {
      final permission = await _locationService.requestPermission();
      final enabled = await _locationService.isServiceEnabled();
      if (mounted) {
        setState(() {
          _permission = permission;
          _locationEnabled = enabled;
        });
      }
    } catch (_) {
      if (mounted) _showError(context.tr('Could not update location access.'));
    }
  }

  Future<void> _logout() async {
    final confirmed = await _confirm(
      context.tr('Log out'),
      context.tr('Are you sure you want to log out?'),
    );
    if (confirmed && mounted) await context.read<AuthController>().logout();
  }

  Future<void> _deactivate() async {
    final confirmed = await _confirm(
      context.tr('Deactivate account'),
      '${context.tr('Your account will be disabled. Your collection and transaction history will be preserved.')}\n\n${context.tr('This action cannot be undone from the app. Continue?')}',
    );
    if (!confirmed || !mounted) return;
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      await context.read<HomeUserRepository>().deactivateAccount(token);
      if (mounted) await context.read<AuthController>().logout();
    } on ApiException catch (e) {
      if (mounted) _showError(e.message);
    } catch (_) {
      if (mounted) _showError(context.tr('Could not save your profile.'));
    }
  }

  Future<bool> _confirm(String title, String message) async {
    return await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: Text(title),
            content: Text(message),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: Text(context.tr('Cancel')),
              ),
              ElevatedButton(
                onPressed: () => Navigator.pop(dialogContext, true),
                child: Text(context.tr('Confirm')),
              ),
            ],
          ),
        ) ??
        false;
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.tr(message))));
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: Text(context.tr('Settings'))),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    if (_error != null || _profile == null) {
      return Scaffold(
        appBar: AppBar(title: Text(context.tr('Settings'))),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(context.tr(_error ?? 'No profile found.')),
              const SizedBox(height: 12),
              OutlinedButton(onPressed: _load, child: Text(context.tr('Retry'))),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Settings'))),
      body: ListView(
        children: [
          _sectionTitle(context.tr('Preferences')),
          LanguageSettingTile(onChanged: _saveLanguagePreference),
          ListTile(
            leading: const Icon(Icons.notifications_outlined),
            title: Text(context.tr('Notification preferences')),
          ),
          SwitchListTile(
            title: Text(context.tr('Collection request updates')),
            value: _preference('collection_updates'),
            onChanged: _savingPreference ? null : (value) => _updatePreference('collection_updates', value),
          ),
          SwitchListTile(
            title: Text(context.tr('Status updates')),
            value: _preference('status_updates'),
            onChanged: _savingPreference ? null : (value) => _updatePreference('status_updates', value),
          ),
          SwitchListTile(
            title: Text(context.tr('Important account updates')),
            value: _preference('account_updates'),
            onChanged: _savingPreference ? null : (value) => _updatePreference('account_updates', value),
          ),
          _sectionTitle(context.tr('Location')),
          ListTile(
            leading: const Icon(Icons.location_on_outlined),
            title: Text(context.tr('Location permission')),
            subtitle: Text(_permissionAllowed
                ? context.tr('Allowed')
                : context.tr('Not allowed')),
          ),
          ListTile(
            leading: const Icon(Icons.gps_fixed),
            title: Text(context.tr('Location services')),
            subtitle: Text(_locationEnabled == true
                ? context.tr('Enabled')
                : context.tr('Disabled')),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Text(context.tr('Location is used for collection-related functionality.')),
          ),
          if (!_permissionAllowed || _locationEnabled != true)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: OutlinedButton.icon(
                onPressed: _requestLocation,
                icon: const Icon(Icons.location_searching),
                label: Text(context.tr('Request location access')),
              ),
            ),
          _sectionTitle(context.tr('Privacy & Consent')),
          _privacyText(context.tr('Camera and photo access is used to identify e-waste items and create collection requests.')),
          _privacyText(context.tr('Location access is used to capture the collection location when you request collection.')),
          _privacyText(context.tr('Your collection request data is used to arrange and verify safe collection.')),
          _sectionTitle(context.tr('Security')),
          ListTile(
            leading: const Icon(Icons.logout),
            title: Text(context.tr('Log out')),
            onTap: _logout,
          ),
          ListTile(
            leading: const Icon(Icons.person_off_outlined),
            title: Text(context.tr('Deactivate account')),
            onTap: _deactivate,
          ),
          _sectionTitle(context.tr('About Kabadiwala Connect')),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: Text(context.tr('About Kabadiwala Connect')),
            subtitle: Text(context.tr('Version 1.0.0')),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  bool get _permissionAllowed =>
      _permission == LocationPermission.always || _permission == LocationPermission.whileInUse;

  Widget _sectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      child: Text(title, style: Theme.of(context).textTheme.titleMedium),
    );
  }

  Widget _privacyText(String text) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      child: Text(text),
    );
  }
}
