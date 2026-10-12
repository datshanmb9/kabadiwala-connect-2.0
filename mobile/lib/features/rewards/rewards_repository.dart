import '../../core/api_client.dart';
import 'models/reward.dart';
import 'models/reward_transaction.dart';

class RewardsRepository {
  final ApiClient apiClient;

  RewardsRepository({required this.apiClient});

  Future<List<Reward>> listMyRewards(String accessToken) async {
    final json = await apiClient.get('/api/v1/rewards/mine', token: accessToken);
    return (json['rewards'] as List<dynamic>? ?? [])
        .map((r) => Reward.fromJson(r as Map<String, dynamic>))
        .toList();
  }

  Future<RewardTransactionPage> listMyTransactions({
    required String accessToken,
    int limit = 20,
    int offset = 0,
  }) async {
    final json = await apiClient.get(
      '/api/v1/rewards/transactions/mine?limit=$limit&offset=$offset',
      token: accessToken,
    );
    return RewardTransactionPage.fromJson(json);
  }

  Future<RewardTransactionSummary> transactionSummary(String accessToken) async {
    final json = await apiClient.get(
      '/api/v1/rewards/transactions/summary/mine',
      token: accessToken,
    );
    return RewardTransactionSummary.fromJson(json);
  }

  /// Requests a MOCK UPI payout for one already-credited reward. Never
  /// sends a UPI PIN or banking password — there is no field for one;
  /// the backend already knows the account's on-file upi_id.
  Future<RewardTransaction> redeem({
    required String rewardId,
    required String accessToken,
    required String idempotencyKey,
  }) async {
    final json = await apiClient.post(
      '/api/v1/rewards/$rewardId/redeem',
      token: accessToken,
      idempotencyKey: idempotencyKey,
    );
    return RewardTransaction.fromJson(json);
  }
}
