import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../features/auth/auth_controller.dart';
import '../features/ewaste/ewaste_repository.dart';
import '../features/ewaste/models/submission.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import '../shared/submission_status.dart';
import 'submission_detail_screen.dart';

class SubmissionsListScreen extends StatefulWidget {
  const SubmissionsListScreen({super.key});

  @override
  State<SubmissionsListScreen> createState() => _SubmissionsListScreenState();
}

class _SubmissionsListScreenState extends State<SubmissionsListScreen> {
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
          .listSubmissions(token);
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
      appBar: AppBar(title: Text(context.tr('My Submissions'))),
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
        children: [
          const SizedBox(height: 80),
          EmptyView(
            message: context.tr('No submissions yet. Submit your first e-waste item from the dashboard.'),
            icon: Icons.recycling,
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
        final info = submissionStatusInfo(s.status, translate: context.tr);
        final details = [
          '${context.tr('Ward:')} ${s.wardId}',
          if (s.category != null) s.category!,
          if (s.condition != null) '${context.tr('Condition:')} ${s.condition}',
          if (s.approximateWeightKg != null)
            '${s.approximateWeightKg!.toStringAsFixed(2)} kg ${context.tr('approx.')}',
          if (s.assignedCollectorId != null)
            '${context.tr('Collector:')} ${s.assignedCollectorId}',
          if (s.priceEstimate != null)
            '${context.tr('Estimate:')} ₹${s.priceEstimate!.minPrice.toStringAsFixed(2)}–₹${s.priceEstimate!.maxPrice.toStringAsFixed(2)}/kg',
        ].join(' · ');
        return Card(
          child: ListTile(
            title: Text('${context.tr('Submission')} ${s.submissionId.substring(0, 8)}…'),
            subtitle: Text(details),
            trailing: Chip(
              label: Text(
                info.label,
                style: const TextStyle(color: Colors.white, fontSize: 12),
              ),
              backgroundColor: info.color,
            ),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) =>
                    SubmissionDetailScreen(submissionId: s.submissionId),
              ),
            ),
          ),
        );
      },
    );
  }
}
