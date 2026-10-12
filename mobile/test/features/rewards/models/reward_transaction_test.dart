import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/features/rewards/models/reward_transaction.dart';

void main() {
  test('RewardTransaction.fromJson parses a SUCCEEDED redemption', () {
    final txn = RewardTransaction.fromJson({
      'txn_id': 'txn-1',
      'home_user_id': 'user-1',
      'reward_id': 'rwd-1',
      'type': 'REDEMPTION',
      'amount': '5.00',
      'status': 'SUCCEEDED',
      'created_at': '2026-09-01T00:00:00',
    });
    expect(txn.type, 'REDEMPTION');
    expect(txn.succeeded, isTrue);
  });

  test('RewardTransaction.fromJson parses a FAILED redemption', () {
    final txn = RewardTransaction.fromJson({
      'txn_id': 'txn-1',
      'home_user_id': 'user-1',
      'reward_id': 'rwd-1',
      'type': 'REDEMPTION',
      'amount': '5.00',
      'status': 'FAILED',
      'created_at': '2026-09-01T00:00:00',
    });
    expect(txn.succeeded, isFalse);
  });
}
