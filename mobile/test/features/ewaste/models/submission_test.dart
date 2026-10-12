import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/features/ewaste/models/submission.dart';

void main() {
  test('Submission.fromJson parses the full list-endpoint shape', () {
    final submission = Submission.fromJson({
      'submission_id': 'sub-1',
      'home_user_id': 'user-1',
      'ward_id': 'WARD-1',
      'photo_file_id': 'local-photo:abc',
      'home_lat': 12.9716,
      'home_lng': 77.5946,
      'home_ts': '2026-01-10T12:00:00',
      'status': 'WAITING_FOR_COLLECTION',
      'created_at': '2026-01-10T12:00:01',
      'updated_at': '2026-01-10T12:00:01',
    });
    expect(submission.submissionId, 'sub-1');
    expect(submission.status, 'WAITING_FOR_COLLECTION');
    expect(submission.homeLat, 12.9716);
    expect(submission.photoFileId, 'local-photo:abc');
    expect(submission.createdAt, isNotNull);
  });

  test('Submission.fromJson parses the narrower detail-endpoint shape (no photo_file_id/created_at)', () {
    final submission = Submission.fromJson({
      'submission_id': 'sub-1',
      'home_user_id': 'user-1',
      'ward_id': 'WARD-1',
      'status': 'COLLECTED',
      'home_lat': 12.9716,
      'home_lng': 77.5946,
      'home_ts': '2026-01-10T12:00:00',
    });
    expect(submission.status, 'COLLECTED');
    expect(submission.photoFileId, isNull);
    expect(submission.createdAt, isNull);
  });

  test('SubmissionCreateResult.fromJson parses the create-endpoint response', () {
    final result = SubmissionCreateResult.fromJson({
      'submission_id': 'sub-1',
      'status': 'WAITING_FOR_COLLECTION',
    });
    expect(result.submissionId, 'sub-1');
    expect(result.status, 'WAITING_FOR_COLLECTION');
  });

  test('Submission.fromJson parses persisted YOLO classification metadata', () {
    final submission = Submission.fromJson({
      'submission_id': 'sub-1',
      'home_user_id': 'user-1',
      'ward_id': 'WARD-1',
      'status': 'CLASSIFIED',
      'home_ts': '2026-01-10T12:00:00',
      'ai_classification': {
        'detected_class': 'TV-Remote-Control',
        'confidence': 0.95,
        'object_count': 1,
        'detections': [
          {'bounding_box': [1, 2, 3, 4]},
        ],
      },
    });

    expect(submission.aiClassification?.detectedClass, 'TV-Remote-Control');
    expect(submission.aiClassification?.objectCount, 1);
    expect(submission.aiClassification?.boundingBoxes.single, [1, 2, 3, 4]);
  });

  group('PriceEstimate total range', () {
    Map<String, dynamic> estimateJson({bool withRange = true}) => {
          'predicted_price_per_kg': 109.12,
          'min_price': 98.21,
          'max_price': 120.03,
          'estimated_total_value': 43.65,
          if (withRange) 'estimated_total_min': 39.28,
          if (withRange) 'estimated_total_max': 48.01,
          'product_type': 'e-waste-small-appliances',
          'condition': 'Used',
          'weight_kg': 0.40,
          'is_estimate': true,
        };

    test('parses and displays the backend total range as-is', () {
      final estimate = PriceEstimate.fromJson(estimateJson());
      expect(estimate.minPrice, 98.21);
      expect(estimate.maxPrice, 120.03);
      expect(estimate.weightKg, 0.40);
      expect(estimate.estimatedTotalMin, 39.28);
      expect(estimate.estimatedTotalMax, 48.01);
      expect(estimate.pricePerKgLabel, '₹98.21 – ₹120.03 / kg');
      expect(estimate.estimatedTotalLabel, '₹39.28 – ₹48.01');
      expect(estimate.toJson()['estimated_total_min'], 39.28);
      expect(estimate.toJson()['estimated_total_max'], 48.01);
    });

    test('older estimates without a range still parse', () {
      final estimate = PriceEstimate.fromJson(estimateJson(withRange: false));
      expect(estimate.estimatedTotalMin, isNull);
      expect(estimate.estimatedTotalLabel, '₹43.65');
    });

    test('pending-collection list item carries the stored estimate', () {
      final submission = Submission.fromJson({
        'submission_id': 'sub-1',
        'home_user_id': 'user-1',
        'ward_id': 'WARD-1',
        'status': 'WAITING_FOR_COLLECTION',
        'price_estimate': estimateJson(),
      });
      expect(submission.priceEstimate?.estimatedTotalLabel, '₹39.28 – ₹48.01');
      expect(
        submission.copyWith(status: 'COLLECTOR_ACCEPTED').priceEstimate?.estimatedTotalMax,
        48.01,
      );
    });
  });
}
