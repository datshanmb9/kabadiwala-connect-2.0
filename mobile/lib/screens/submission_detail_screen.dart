import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../features/auth/auth_controller.dart';
import '../features/ewaste/ewaste_repository.dart';
import '../features/ewaste/models/submission.dart';
import '../features/pricing/widgets/price_trend_card.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import '../shared/submission_status.dart';

class SubmissionDetailScreen extends StatefulWidget {
  final String submissionId;
  const SubmissionDetailScreen({super.key, required this.submissionId});

  @override
  State<SubmissionDetailScreen> createState() => _SubmissionDetailScreenState();
}

class _SubmissionDetailScreenState extends State<SubmissionDetailScreen> {
  bool _loading = true;
  String? _error;
  Submission? _submission;

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
      final submission = await context.read<EwasteRepository>().getSubmission(
        widget.submissionId,
        token,
      );
      if (!mounted) return;
      setState(() {
        _submission = submission;
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
      appBar: AppBar(title: Text(context.tr('Submission Detail'))),
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
    final s = _submission;
    if (s == null) {
      return ListView(
        children: [
          const SizedBox(height: 80),
          EmptyView(message: context.tr('Submission not found.')),
        ],
      );
    }
    final info = submissionStatusInfo(s.status, translate: context.tr);
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
                  context.tr('Submission ID'),
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                Text(s.submissionId),
                const SizedBox(height: 16),
                Text(context.tr('Status'), style: Theme.of(context).textTheme.labelMedium),
                const SizedBox(height: 4),
                Chip(
                  label: Text(
                    info.label,
                    style: const TextStyle(color: Colors.white),
                  ),
                  backgroundColor: info.color,
                ),
                const SizedBox(height: 16),
                Text(context.tr('Ward'), style: Theme.of(context).textTheme.labelMedium),
                Text(s.wardId),
                if (s.category != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    context.tr('Material/category'),
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  Text(s.category!),
                ],
                if (s.condition != null) ...[
                  const SizedBox(height: 16),
                  Text(context.tr('Condition'), style: Theme.of(context).textTheme.labelMedium),
                  Text(s.condition!),
                ],
                if (s.priceEstimate != null) ...[
                  const SizedBox(height: 16),
                  Text(context.tr('Price estimation'), style: Theme.of(context).textTheme.labelMedium),
                  Text(
                    '₹${s.priceEstimate!.minPrice.toStringAsFixed(2)} – '
                    '₹${s.priceEstimate!.maxPrice.toStringAsFixed(2)} / kg',
                  ),
                  Text(
                    '${context.tr('Estimated total:')} ${s.priceEstimate!.estimatedTotalLabel}',
                  ),
                  PriceTrendCard(item: s.category ?? s.priceEstimate!.productType, wardId: s.wardId),
                ],
                if (s.aiClassification != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    context.tr('YOLO classification'),
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  if (s.aiClassification!.detectedClass != null)
                    Text('${context.tr('Detected:')} ${s.aiClassification!.detectedClass}'),
                  if (s.aiClassification!.confidence != null)
                    Text(
                      '${context.tr('Confidence:')} ${(s.aiClassification!.confidence! * 100).toStringAsFixed(1)}%',
                    ),
                  Text('${context.tr('Objects:')} ${s.aiClassification!.objectCount}'),
                  Text(
                    '${context.tr('Bounding boxes:')} ${s.aiClassification!.boundingBoxes.length}',
                  ),
                ],
                if (s.approximateWeightKg != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    context.tr('Approximate weight'),
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  Text('${s.approximateWeightKg!.toStringAsFixed(2)} kg'),
                ],
                if (s.actualWeightKg != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    context.tr('Actual collected weight'),
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  Text('${s.actualWeightKg!.toStringAsFixed(2)} kg'),
                ],
                if (s.assignedCollectorId != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    context.tr('Assigned collector'),
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  Text(s.assignedCollectorId!),
                ],
                if (s.homeLat != null && s.homeLng != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    context.tr('Submitted location'),
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  Text(
                    '${s.homeLat!.toStringAsFixed(5)}, ${s.homeLng!.toStringAsFixed(5)}',
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
}
