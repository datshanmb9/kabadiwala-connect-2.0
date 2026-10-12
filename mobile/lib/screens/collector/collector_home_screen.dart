import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_exception.dart';
import '../../features/auth/auth_controller.dart';
import '../../features/collector/collector_repository.dart';
import '../../features/collector/models/collector_profile.dart';
import '../../features/translation/translation_text.dart';
import '../../shared/state_views.dart';
import 'collector_accepted_collections_screen.dart';
import 'collector_pending_queue_screen.dart';

/// Collector's own nav root — deliberately has no route to any Home User
/// screen (registration, submit-e-waste, home-user profile). Role
/// isolation for this app is enforced by AuthGate never constructing this
/// widget for a HOME_USER session (and vice versa); the actual security
/// boundary is backend RBAC, unchanged by any of this.
class CollectorHomeScreen extends StatefulWidget {
  const CollectorHomeScreen({super.key});

  @override
  State<CollectorHomeScreen> createState() => _CollectorHomeScreenState();
}

class _CollectorHomeScreenState extends State<CollectorHomeScreen> {
  bool _loading = true;
  String? _error;
  CollectorProfile? _profile;

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
      final profile = await context.read<CollectorRepository>().getProfile(
        token,
      );
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

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    return Scaffold(
      appBar: AppBar(
        title: Text(context.tr('Collector Dashboard')),
        actions: [
          IconButton(
            key: const Key('collector_logout_button'),
            icon: const Icon(Icons.logout),
            tooltip: context.tr('Logout'),
            onPressed: () => auth.logout(),
          ),
        ],
      ),
      body: RefreshIndicator(onRefresh: _loadProfile, child: _buildBody()),
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
        children: const [
          SizedBox(height: 80),
          EmptyView(
            message: 'No collector profile found.',
            icon: Icons.person_off,
          ),
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
                Text(
                  '${context.tr('Employee ID:')} ${profile.employeeId}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const Divider(height: 24),
                _InfoRow(
                  icon: Icons.map_outlined,
                  label: context.tr('Assigned Ward'),
                  value: profile.wardId,
                ),
                if (profile.rrrId != null)
                  _InfoRow(
                    icon: Icons.factory_outlined,
                    label: context.tr('RRR Centre'),
                    value: profile.rrrId!,
                  ),
                if (profile.assignedAreaRadiusM != null)
                  _InfoRow(
                    icon: Icons.radar,
                    label: context.tr('Assigned Area Radius'),
                    value:
                        '${profile.assignedAreaRadiusM!.toStringAsFixed(0)} m',
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),
        ElevatedButton.icon(
          key: const Key('view_pending_queue_button'),
          icon: const Icon(Icons.inbox_outlined),
          label: Text(context.tr('Pending Collections')),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => const CollectorPendingQueueScreen(),
            ),
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          key: const Key('view_assigned_queue_button'),
          icon: const Icon(Icons.local_shipping_outlined),
          label: Text(context.tr('My Assigned Pickups')),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) =>
                  const CollectorPendingQueueScreen(assignedOnly: true),
            ),
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          key: const Key('view_accepted_collections_button'),
          icon: const Icon(Icons.assignment_turned_in_outlined),
          label: Text(context.tr('Accepted Collections')),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => const CollectorAcceptedCollectionsScreen(),
            ),
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

  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
  });

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
