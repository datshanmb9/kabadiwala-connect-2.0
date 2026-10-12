import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_exception.dart';
import '../../features/auth/auth_controller.dart';
import '../../features/ewaste/ewaste_repository.dart';
import '../../features/ewaste/models/submission.dart';
import '../../features/translation/translation_text.dart';
import '../../shared/submission_status.dart';
import '../../shared/state_views.dart';
import 'collector_lot_detail_screen.dart';

/// Post-handover list: every submission this collector has already handed
/// over (status COLLECTED or later), each one now tracking its own
/// auto-created lot through bidding. Real backend data only — an empty
/// list is shown as an empty state, never simulated rows.
class CollectorAcceptedCollectionsScreen extends StatefulWidget {
  const CollectorAcceptedCollectionsScreen({super.key});

  @override
  State<CollectorAcceptedCollectionsScreen> createState() =>
      _CollectorAcceptedCollectionsScreenState();
}

class _CollectorAcceptedCollectionsScreenState
    extends State<CollectorAcceptedCollectionsScreen> {
  bool _loading = true;
  String? _error;
  List<Submission> _submissions = [];

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
      final submissions = await context
          .read<EwasteRepository>()
          .listHandedOverForCollector(token);
      if (!mounted) return;
      setState(() {
        _submissions = submissions;
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
    return Scaffold(
      appBar: AppBar(title: Text(context.tr('Accepted Collections'))),
      body: RefreshIndicator(onRefresh: _load, child: _buildBody()),
    );
  }

  Widget _buildBody() {
    if (_loading) return const LoadingView();
    if (_error != null) {
      return ListView(
        children: [
          const SizedBox(height: 80),
          ErrorView(message: _error!, onRetry: _load),
        ],
      );
    }
    if (_submissions.isEmpty) {
      return ListView(
        children: const [
          SizedBox(height: 80),
          EmptyView(
            message: 'No accepted collections yet. Confirm a handover to see it here.',
            icon: Icons.assignment_turned_in_outlined,
          ),
        ],
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _submissions.length,
      separatorBuilder: (_, _) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final s = _submissions[index];
        return Card(
          child: ListTile(
            leading: const Icon(Icons.recycling),
            title: Text(s.category ?? '${context.tr('Submission')} ${s.submissionId.substring(0, 8)}…'),
            subtitle: Text(_subtitleFor(s)),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              if (s.lotId == null) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      context.tr(
                        "This collection has no material/category on record yet, so it hasn't been auto-listed for bidding.",
                      ),
                    ),
                  ),
                );
                return;
              }
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => CollectorLotDetailScreen(lotId: s.lotId!),
                ),
              );
            },
          ),
        );
      },
    );
  }

  String _subtitleFor(Submission s) {
    final weight = s.actualWeightKg ?? s.approximateWeightKg;
    final parts = <String>[
      submissionStatusInfo(s.status, translate: context.tr).label,
      if (s.condition != null) context.tr(s.condition!),
      if (weight != null) '${weight.toStringAsFixed(2)} kg',
    ];
    return parts.join(' · ');
  }
}
