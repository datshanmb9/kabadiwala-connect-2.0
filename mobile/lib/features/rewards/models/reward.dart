/// Mirrors the backend's RewardResponse shape exactly (see
/// backend/app/modules/rewards/schemas.py). `amount` stays a decimal
/// STRING end to end — never parsed to a Dart double — matching the
/// same "money is Decimal128/string, never float" rule used everywhere
/// else in this app's money-adjacent code.
class Reward {
  final String rewardId;
  final String homeUserId;
  final String period;
  final int points;
  final String amount;
  final String status;
  final String createdAt;

  const Reward({
    required this.rewardId,
    required this.homeUserId,
    required this.period,
    required this.points,
    required this.amount,
    required this.status,
    required this.createdAt,
  });

  bool get isRedeemable => status == 'CREDITED';

  factory Reward.fromJson(Map<String, dynamic> json) => Reward(
        rewardId: json['reward_id'] as String,
        homeUserId: json['home_user_id'] as String,
        period: json['period'] as String,
        points: json['points'] as int,
        amount: json['amount'] as String,
        status: json['status'] as String,
        createdAt: json['created_at'] as String,
      );
}
