import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../features/auth/auth_controller.dart';
import '../features/home_user/home_user_repository.dart';
import '../features/home_user/models/home_user_profile.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import 'edit_profile_screen.dart';
import 'user_settings_screen.dart';

class UserProfileScreen extends StatefulWidget {
  const UserProfileScreen({super.key});

  @override
  State<UserProfileScreen> createState() => _UserProfileScreenState();
}

class _UserProfileScreenState extends State<UserProfileScreen> {
  HomeUserProfile? _profile;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      final profile = await context.read<HomeUserRepository>().getProfile(token);
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  Future<void> _editProfile() async {
    final profile = _profile;
    if (profile == null) return;
    final updated = await Navigator.of(context).push<HomeUserProfile>(
      MaterialPageRoute(builder: (_) => EditProfileScreen(profile: profile)),
    );
    if (!mounted || updated == null) return;
    setState(() => _profile = updated);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(context.tr('Profile updated successfully.'))),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(context.tr('Profile')),
        actions: [
          IconButton(
            key: const Key('profile_settings_button'),
            icon: const Icon(Icons.settings_outlined),
            tooltip: context.tr('Settings'),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const UserSettingsScreen()),
            ),
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) return LoadingView(message: context.tr('Loading your profile...'));
    if (_error != null) {
      return ErrorView(
        message: _error!,
        onRetry: _loadProfile,
      );
    }
    final profile = _profile;
    if (profile == null) {
      return EmptyView(message: context.tr('No profile found.'), icon: Icons.person_off);
    }

    return RefreshIndicator(
      onRefresh: _loadProfile,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 36,
                    child: Text(
                      profile.fullName.isEmpty ? '?' : profile.fullName[0].toUpperCase(),
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(profile.fullName, style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 4),
                  Text('@${profile.username}', style: const TextStyle(color: Colors.grey)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(context.tr('Account information'), style: Theme.of(context).textTheme.titleMedium),
                  const Divider(height: 24),
                  _InfoRow(label: context.tr('Name'), value: profile.fullName),
                  _InfoRow(label: context.tr('User ID'), value: profile.userId),
                  _InfoRow(label: context.tr('Account status'), value: context.tr(profile.accountStatus)),
                  _InfoRow(label: context.tr('Address'), value: profile.address),
                  _InfoRow(label: context.tr('Ward'), value: profile.wardId),
                  if (profile.createdAt != null)
                    _InfoRow(
                      label: context.tr('Member since'),
                      value: profile.createdAt!.toLocal().toString().split(' ').first,
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            key: const Key('edit_profile_button'),
            icon: const Icon(Icons.edit_outlined),
            label: Text(context.tr('Edit Profile')),
            onPressed: _editProfile,
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            key: const Key('profile_open_settings_button'),
            icon: const Icon(Icons.settings_outlined),
            label: Text(context.tr('Settings')),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const UserSettingsScreen()),
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$label: ', style: const TextStyle(fontWeight: FontWeight.w600)),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
