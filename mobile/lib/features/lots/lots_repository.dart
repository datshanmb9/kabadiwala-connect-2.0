import '../../core/api_client.dart';
import 'models/lot.dart';

/// Collector-facing view of the same lots/bids architecture recycler-web
/// already uses — no duplicate backend API, just the collector's own
/// authorized slice of GET /lots/{id}, GET /lots/{id}/bids, and
/// POST /bids/{id}/accept (the "select recycler" action).
class LotsRepository {
  final ApiClient apiClient;

  LotsRepository({required this.apiClient});

  Future<Lot> getLot({required String accessToken, required String lotId}) async {
    final json = await apiClient.get('/api/v1/lots/$lotId', token: accessToken);
    return Lot.fromJson(json);
  }

  Future<List<Bid>> listBidsForLot({
    required String accessToken,
    required String lotId,
  }) async {
    final json = await apiClient.get('/api/v1/lots/$lotId/bids', token: accessToken);
    return (json['bids'] as List<dynamic>? ?? [])
        .map((b) => Bid.fromJson(b as Map<String, dynamic>))
        .toList();
  }

  /// "Confirm Recycler": accepts one bid for a lot the caller owns. The
  /// backend enforces single-selection (a partial unique index on
  /// bids.lot_id where status=ACCEPTED) and implicitly rejects every
  /// sibling PLACED bid on the same lot — this call never does that itself.
  Future<Bid> selectRecycler({
    required String accessToken,
    required String bidId,
    required String idempotencyKey,
  }) async {
    final json = await apiClient.post(
      '/api/v1/bids/$bidId/accept',
      token: accessToken,
      idempotencyKey: idempotencyKey,
    );
    return Bid.fromJson(json);
  }
}
