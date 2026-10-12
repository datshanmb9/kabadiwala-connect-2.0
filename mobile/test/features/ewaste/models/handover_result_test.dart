import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/features/ewaste/models/handover_result.dart';

void main() {
  test('HandoverResult.fromJson parses a VERIFIED result', () {
    final result = HandoverResult.fromJson({
      'submission_id': 'sub-1',
      'status': 'COLLECTED',
      'verification_result': 'VERIFIED',
      'distance_m': 12.5,
      'reasons': [],
    });
    expect(result.status, 'COLLECTED');
    expect(result.isVerified, isTrue);
    expect(result.distanceM, 12.5);
    expect(result.reasons, isEmpty);
  });

  test('HandoverResult.fromJson parses a FLAGGED result with reasons', () {
    final result = HandoverResult.fromJson({
      'submission_id': 'sub-1',
      'status': 'FLAGGED_FOR_REVIEW',
      'verification_result': 'FLAGGED',
      'distance_m': 500.0,
      'reasons': ['DISTANCE_EXCEEDED'],
    });
    expect(result.status, 'FLAGGED_FOR_REVIEW');
    expect(result.isVerified, isFalse);
    expect(result.reasons, contains('DISTANCE_EXCEEDED'));
  });

  test('HandoverResult.fromJson handles a null distance_m (e.g. invalid GPS case)', () {
    final result = HandoverResult.fromJson({
      'submission_id': 'sub-1',
      'status': 'FLAGGED_FOR_REVIEW',
      'verification_result': 'FLAGGED',
      'distance_m': null,
      'reasons': ['INVALID_COLLECTOR_GPS'],
    });
    expect(result.distanceM, isNull);
  });
}
