import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_exception.dart';
import '../../core/idempotency_key_generator.dart';
import '../../features/auth/auth_controller.dart';
import '../../features/ewaste/ewaste_repository.dart';
import '../../features/ewaste/models/submission.dart';
import '../../features/pricing/price_trend.dart';
import '../../features/pricing/widgets/price_trend_card.dart';
import '../../features/translation/translation_text.dart';
import '../../shared/state_views.dart';
import 'collector_handover_screen.dart';

/// Lists submissions awaiting collection in the collector's own ward
/// (server-derived — this screen never asks the collector which ward to
/// browse). Real backend data only; an empty queue is shown as an empty
/// state, never simulated with placeholder rows.
class CollectorPendingQueueScreen extends StatefulWidget {
  final bool assignedOnly;

  const CollectorPendingQueueScreen({super.key, this.assignedOnly = false});

  @override
  State<CollectorPendingQueueScreen> createState() =>
      _CollectorPendingQueueScreenState();
}

class _CollectorPendingQueueScreenState
    extends State<CollectorPendingQueueScreen> {
  bool _loading = true;
  String? _error;
  List<Submission> _submissions = [];
  final Map<String, Future<PriceTrend>> _trends = {};

  Future<PriceTrend> _trendFor(Submission s) {
    final item = s.category ?? s.priceEstimate!.productType;
    return _trends.putIfAbsent(
      '$item|${s.wardId}',
      () => fetchPriceTrend(context, item: item, wardId: s.wardId),
    );
  }

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
      final submissions = widget.assignedOnly
          ? await context.read<EwasteRepository>().listAssignedForCollector(
              token,
            )
          : await context.read<EwasteRepository>().listPendingForCollector(
              token,
            );
      if (!mounted) return;
      setState(() {
        _submissions = submissions;
        _trends.clear();
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
      appBar: AppBar(
        title: Text(
          widget.assignedOnly
              ? context.tr('My Assigned Pickups')
              : context.tr('Available Collections'),
        ),
      ),
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
            message: 'No submissions are waiting for collection in your ward right now.',
            icon: Icons.inbox_outlined,
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
            title: Text('${context.tr('Submission')} ${s.submissionId.substring(0, 8)}…'),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  s.homeTs != null
                      ? '${context.tr('Submitted:')} ${s.homeTs}'
                      : '${context.tr('Ward:')} ${s.wardId}',
                ),
                // The ML estimate already stored on this submission by the
                // backend — never recomputed or re-requested here.
                if (s.priceEstimate != null) ...[
                  Text(
                    '${context.tr('Estimated price:')} ${s.priceEstimate!.pricePerKgLabel}',
                    key: const Key('pending_estimated_price'),
                  ),
                  Text(
                    '${context.tr('Estimated total:')} ${s.priceEstimate!.estimatedTotalLabel}'
                    ' (${s.priceEstimate!.weightKg.toStringAsFixed(2)} kg)',
                    key: const Key('pending_estimated_total'),
                  ),
                  PriceTrendSummaryText(future: _trendFor(s)),
                ],
              ],
            ),
            isThreeLine: s.priceEstimate != null,
            trailing: const Icon(Icons.chevron_right),
            onTap: () async {
              var selected = s;
              if (!widget.assignedOnly) {
                try {
                  final token = context
                      .read<AuthController>()
                      .session
                      ?.accessToken;
                  if (token == null) return;
                  final accepted = await context
                      .read<EwasteRepository>()
                      .acceptSubmission(
                        accessToken: token,
                        submissionId: s.submissionId,
                        idempotencyKey: IdempotencyKeyGenerator.generate(),
                      );
                  selected = s.copyWith(
                    status: accepted.status,
                    assignedCollectorId: accepted.assignedCollectorId,
                  );
                } on ApiException catch (e) {
                  if (context.mounted)
                    ScaffoldMessenger.of(context)
                        .showSnackBar(SnackBar(content: Text(context.tr(e.message))));
                  return;
                }
              }
              final handedOver = await Navigator.of(context).push<bool>(
                MaterialPageRoute(
                  builder: (_) => CollectorHandoverScreen(submission: selected),
                ),
              );
              if (handedOver == true) _load();
            },
          ),
        );
      },
    );
  }
}
