import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../core/location_service.dart';
import '../features/auth/auth_controller.dart';
import '../features/home_user/home_user_repository.dart';
import '../features/home_user/models/home_user_profile.dart';
import '../features/notifications/notifications_repository.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import 'financial_history_screen.dart';
import 'notifications_screen.dart';
import 'rewards_screen.dart';
import 'submissions_list_screen.dart';
import 'submit_ewaste_screen.dart';
import 'user_profile_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _loading = true;
  bool _resolvingLocation = false;
  String? _error;
  HomeUserProfile? _profile;
  String? _locationName;
  int _unreadNotifications = 0;
  final _locationService = LocationService();

  @override
  void initState() {
    super.initState();
    _loadProfile();
    _loadUnreadNotifications();
  }

  Future<void> _loadUnreadNotifications() async {
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      final count = await context.read<NotificationsRepository>().unreadCount(token);
      if (mounted) setState(() => _unreadNotifications = count);
    } catch (_) {
      // The dashboard remains usable when notification loading is unavailable.
    }
  }

  Future<void> _loadProfile() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final auth = context.read<AuthController>();
    final token = auth.session?.accessToken;
    if (token == null) return;
    try {
      final profile = await context.read<HomeUserRepository>().getProfile(token);
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _loading = false;
        _locationName = null;
        _resolvingLocation = true;
      });
      final locationName = await _locationService.getReadableLocationFromCoordinates(
        profile.householdLat,
        profile.householdLng,
      );
      if (!mounted) return;
      setState(() {
        _locationName = locationName;
        _resolvingLocation = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    return Scaffold(
      appBar: AppBar(
        title: Text(context.tr('My Dashboard')),
        actions: [
          IconButton(
            key: const Key('profile_button'),
            icon: const Icon(Icons.person_outline),
            tooltip: context.tr('Profile'),
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const UserProfileScreen()),
              );
              if (mounted) _loadProfile();
            },
          ),
          Stack(
            alignment: Alignment.topRight,
            children: [
              IconButton(
                key: const Key('notifications_button'),
                icon: const Icon(Icons.notifications_none),
                tooltip: context.tr('Notifications'),
                onPressed: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const NotificationsScreen()),
                  );
                  if (mounted) _loadUnreadNotifications();
                },
              ),
              if (_unreadNotifications > 0)
                IgnorePointer(
                  child: Container(
                    key: const Key('notifications_badge'),
                    padding: const EdgeInsets.all(4),
                    constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.error,
                      shape: BoxShape.circle,
                    ),
                    child: Text(
                      _unreadNotifications > 99 ? '99+' : '$_unreadNotifications',
                      style: const TextStyle(color: Colors.white, fontSize: 10),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
            ],
          ),
          IconButton(
            key: const Key('logout_button'),
            icon: const Icon(Icons.logout),
            tooltip: context.tr('Logout'),
            onPressed: () => auth.logout(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadProfile,
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) return const LoadingView(message: 'Loading your profile…');
    if (_error != null) {
      return ListView(
        children: [
          const SizedBox(height: 80),
          ErrorView(message: _error!, onRetry: _loadProfile),
        ],
      );
    }
    final profile = _profile;
    if (profile == null) {
      return ListView(
        children: [
          const SizedBox(height: 80),
          const EmptyView(message: 'No profile found.', icon: Icons.person_off),
        ],
      );
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(profile.fullName, style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 4),
                Text('@${profile.username}', style: const TextStyle(color: Colors.grey)),
                const Divider(height: 24),
                _InfoRow(icon: Icons.home_outlined, label: context.tr('Address'), value: profile.address),
                _InfoRow(icon: Icons.map_outlined, label: context.tr('Ward'), value: profile.wardId),
                _InfoRow(
                  icon: Icons.location_on_outlined,
                  label: context.tr('Household location'),
                  value: _resolvingLocation
                      ? context.tr('Finding city name...')
                      : _locationName ??
                          '${profile.householdLat.toStringAsFixed(5)}, ${profile.householdLng.toStringAsFixed(5)}',
                ),
                if (profile.upiId != null && profile.upiId!.isNotEmpty)
                  _InfoRow(icon: Icons.account_balance_wallet_outlined, label: context.tr('UPI ID'), value: profile.upiId!),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),
        ElevatedButton.icon(
          key: const Key('submit_ewaste_button'),
          icon: const Icon(Icons.camera_alt_outlined),
          label: Text(context.tr('Submit E-Waste')),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => SubmitEwasteScreen(wardId: profile.wardId)),
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          key: const Key('view_submissions_button'),
          icon: const Icon(Icons.history),
          label: Text(context.tr('My Submissions')),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const SubmissionsListScreen()),
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          key: const Key('view_rewards_button'),
          icon: const Icon(Icons.card_giftcard_outlined),
          label: Text(context.tr('My Rewards')),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const RewardsScreen()),
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          key: const Key('view_financial_history_button'),
          icon: const Icon(Icons.receipt_long_outlined),
          label: Text(context.tr('Payments & Transactions')),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const FinancialHistoryScreen()),
          ),
        ),
      ],
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _InfoRow({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: Colors.grey),
          const SizedBox(width: 8),
          Text('$label: ', style: const TextStyle(fontWeight: FontWeight.w600)),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
