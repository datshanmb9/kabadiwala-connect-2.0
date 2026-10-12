/// Mirrors the backend's LotResponse. Exactly one of [rrrId]/
/// [ownerCollectorId] is set — this app only ever deals with the latter
/// (a lot auto-created from the collector's own confirmed handover).
class Lot {
  final String lotId;
  final String? rrrId;
  final String? ownerCollectorId;
  final String wardId;
  final String category;
  final List<String> itemIds;
  final String status;
  final DateTime? bidDeadline;
  final double? totalWeightKg;

  const Lot({
    required this.lotId,
    this.rrrId,
    this.ownerCollectorId,
    required this.wardId,
    required this.category,
    required this.itemIds,
    required this.status,
    this.bidDeadline,
    this.totalWeightKg,
  });

  factory Lot.fromJson(Map<String, dynamic> json) => Lot(
        lotId: json['lot_id'] as String,
        rrrId: json['rrr_id'] as String?,
        ownerCollectorId: json['owner_collector_id'] as String?,
        wardId: json['ward_id'] as String,
        category: json['category'] as String,
        itemIds: (json['item_ids'] as List<dynamic>? ?? [])
            .map((e) => e as String)
            .toList(),
        status: json['status'] as String,
        bidDeadline: json['bid_deadline'] == null
            ? null
            : DateTime.tryParse(json['bid_deadline'] as String),
        totalWeightKg: (json['total_weight_kg'] as num?)?.toDouble(),
      );
}

/// Mirrors the backend's BidResponse exactly — status is always the
/// backend's real value (PLACED/ACCEPTED/REJECTED/CANCELLED), never
/// inferred or simulated client-side.
class Bid {
  final String bidId;
  final String lotId;
  final String recyclerId;
  final String amount;
  final String status;
  final DateTime placedAt;
  final DateTime? acceptedAt;

  const Bid({
    required this.bidId,
    required this.lotId,
    required this.recyclerId,
    required this.amount,
    required this.status,
    required this.placedAt,
    this.acceptedAt,
  });

  factory Bid.fromJson(Map<String, dynamic> json) => Bid(
        bidId: json['bid_id'] as String,
        lotId: json['lot_id'] as String,
        recyclerId: json['recycler_id'] as String,
        amount: json['amount'] as String,
        status: json['status'] as String,
        placedAt: DateTime.parse(json['placed_at'] as String),
        acceptedAt: json['accepted_at'] == null
            ? null
            : DateTime.tryParse(json['accepted_at'] as String),
      );
}
