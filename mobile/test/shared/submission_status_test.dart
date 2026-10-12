import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/shared/submission_status.dart';

void main() {
  test('known backend states map to a human-readable label', () {
    expect(submissionStatusInfo('WAITING_FOR_COLLECTION').label, 'Waiting for Collection');
    expect(submissionStatusInfo('COLLECTED').label, 'Collected');
    expect(submissionStatusInfo('FLAGGED_FOR_REVIEW').label, 'Flagged For Review');
    expect(submissionStatusInfo('COMPLETED').label, 'Completed');
  });

  test('every state in the backend allow-list resolves to a non-empty label', () {
    const allStates = [
      'CREATED', 'PHOTO_CAPTURED', 'WAITING_FOR_COLLECTION', 'COLLECTOR_ASSIGNED',
      'HANDOVER_PENDING', 'LOCATION_VERIFIED', 'COLLECTED', 'AT_RRR', 'CLASSIFIED',
      'LOT_CREATED', 'LISTED_FOR_BIDDING', 'BID_SELECTED', 'LOGISTICS_BOOKED',
      'READY_FOR_COLLECTION', 'PAYMENT_PENDING', 'PAID', 'COMPLETED',
      'FLAGGED_FOR_REVIEW', 'REJECTED',
    ];
    for (final state in allStates) {
      expect(submissionStatusInfo(state).label, isNotEmpty, reason: 'state=$state');
    }
  });

  test('an unrecognized status still produces a readable fallback label instead of crashing', () {
    final info = submissionStatusInfo('SOME_FUTURE_STATE');
    expect(info.label, 'Some Future State');
  });
}
