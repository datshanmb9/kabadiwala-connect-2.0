import 'package:flutter/material.dart';

import '../../safety/safety_service.dart';
import '../../translation/translation_text.dart';
import '../models/submission.dart';

/// Result of the existing YOLO photo detection (POST /api/v1/ai/classify-photo),
/// shared by the Home User submission and Collector handover screens so both
/// show the same thing.
class PhotoDetectionResult extends StatelessWidget {
  final PhotoClassificationResult result;

  const PhotoDetectionResult({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final itemName = result.detectedItemName;
    if (result.needsReview || result.category == null || itemName == null) {
      return Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text(
          result.failureReason == null
              ? context.tr('No confident e-waste object detected. You can enter the category manually.')
              : '${context.tr('Prediction needs review:')} ${result.failureReason}',
          key: const Key('photo_detection_needs_review'),
          style: const TextStyle(color: Colors.orange),
        ),
      );
    }
    final details = [
      if (result.confidence != null)
        '${context.tr('Confidence:')} ${(result.confidence! * 100).toStringAsFixed(1)}%',
      '${context.tr('Objects detected:')} ${result.objectCount}',
    ].join(' · ');
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${context.tr('Detected item:')} $itemName',
            key: const Key('photo_detected_item'),
            style: const TextStyle(color: Colors.green, fontWeight: FontWeight.w600),
          ),
          Text(details, style: const TextStyle(color: Colors.green)),
          // The backend picks the highest-confidence detection as the item.
          if (result.objectCount > 1)
            Text(
              context.tr('Several objects were found; showing the most confident one.'),
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      ),
    );
  }
}

/// Safety instructions for [itemName], from the existing SafetyService.
/// [onContinue] adds the acknowledgement button the Home User flow uses.
class SafetyMeasuresCard extends StatelessWidget {
  final String itemName;
  final VoidCallback? onContinue;

  static final _safetyService = SafetyService();

  const SafetyMeasuresCard({super.key, required this.itemName, this.onContinue});

  @override
  Widget build(BuildContext context) {
    final content = _safetyService.forCategory(itemName);
    return Card(
      key: const Key('safety_measures_card'),
      margin: const EdgeInsets.only(top: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(context.tr('Safety Measures'), style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text('${context.tr('Material:')} ${itemName.trim()}'),
            const SizedBox(height: 12),
            Text(
              context.tr(content.title),
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 4),
            ...content.instructions.map(
              (instruction) => Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('• '),
                    Expanded(child: Text(context.tr(instruction))),
                  ],
                ),
              ),
            ),
            if (onContinue != null) ...[
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  key: const Key('safety_continue_button'),
                  onPressed: onContinue,
                  child: Text(context.tr('Continue')),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
