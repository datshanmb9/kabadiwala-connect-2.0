/// Mirrors the backend's RewardTransactionResponse shape exactly — the
/// result of a redemption attempt through the MOCK UPI payout. Never
/// carries a PIN/password field; there is none to carry.
class RewardTransaction {
  final String txnId;
  final String homeUserId;
  final String rewardId;
  final String type; // "CREDIT" or "REDEMPTION"
  final String amount;
  final String status;
  final String createdAt;

  const RewardTransaction({
    required this.txnId,
    required this.homeUserId,
    required this.rewardId,
    required this.type,
    required this.amount,
    required this.status,
    required this.createdAt,
  });

  bool get succeeded => status == 'SUCCEEDED';
  bool get isCredit => type == 'CREDIT';

  factory RewardTransaction.fromJson(Map<String, dynamic> json) => RewardTransaction(
        txnId: json['txn_id'] as String,
        homeUserId: json['home_user_id'] as String,
        rewardId: json['reward_id'] as String,
        type: json['type'] as String,
        amount: json['amount'] as String,
        status: json['status'] as String,
        createdAt: json['created_at'] as String,
      );
}

    class RewardTransactionPage {
      final List<RewardTransaction> transactions;
      final bool hasMore;

      const RewardTransactionPage({required this.transactions, required this.hasMore});

      factory RewardTransactionPage.fromJson(Map<String, dynamic> json) => RewardTransactionPage(
            transactions: (json['transactions'] as List<dynamic>? ?? [])
                .map((item) => RewardTransaction.fromJson(item as Map<String, dynamic>))
                .toList(),
            hasMore: json['has_more'] as bool? ?? false,
          );
    }

    class RewardTransactionSummary {
      final String completedCredits;
      final String completedRedemptions;
      final String pendingAmount;
      final int failedCount;

      const RewardTransactionSummary({
        required this.completedCredits,
        required this.completedRedemptions,
        required this.pendingAmount,
        required this.failedCount,
      });

      factory RewardTransactionSummary.fromJson(Map<String, dynamic> json) => RewardTransactionSummary(
            completedCredits: json['completed_credits'] as String,
            completedRedemptions: json['completed_redemptions'] as String,
            pendingAmount: json['pending_amount'] as String,
            failedCount: json['failed_count'] as int? ?? 0,
          );
    }
