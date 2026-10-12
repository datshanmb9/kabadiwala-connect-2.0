import 'package:flutter_test/flutter_test.dart';
import 'package:kabadiwala_mobile/features/rewards/models/reward.dart';

void main() {
  test('Reward.fromJson parses a CREDITED reward and keeps amount as a string', () {
    final reward = Reward.fromJson({
      'reward_id': 'rwd-1',
      'home_user_id': 'user-1',
      'period': '2026-09',
      'points': 10,
      'amount': '5.00',
      'status': 'CREDITED',
      'created_at': '2026-09-01T00:00:00',
    });
    expect(reward.points, 10);
    expect(reward.amount, '5.00');
    expect(reward.amount, isA<String>());
    expect(reward.isRedeemable, isTrue);
  });

  test('a REDEEMED reward is not redeemable', () {
    final reward = Reward.fromJson({
      'reward_id': 'rwd-1',
      'home_user_id': 'user-1',
      'period': '2026-09',
      'points': 10,
      'amount': '5.00',
      'status': 'REDEEMED',
      'created_at': '2026-09-01T00:00:00',
    });
    expect(reward.isRedeemable, isFalse);
  });
}
