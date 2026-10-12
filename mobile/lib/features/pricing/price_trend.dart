/// Response of GET /api/v1/pricing/trend: historical INR/kg for an item,
/// built by the backend from real accepted sales on the platform. The app
/// only displays it — no trend is computed or invented client-side.
class PriceTrendPoint {
  final DateTime date;
  final double pricePerKg;
  final int sales;

  const PriceTrendPoint({required this.date, required this.pricePerKg, required this.sales});

  factory PriceTrendPoint.fromJson(Map<String, dynamic> json) => PriceTrendPoint(
        date: DateTime.parse(json['date'] as String),
        pricePerKg: (json['price_per_kg'] as num).toDouble(),
        sales: (json['sales'] as num?)?.toInt() ?? 1,
      );
}

class PriceTrend {
  final String item;
  final String? wardId;
  final String scope; // 'ward' | 'all_wards'
  final int windowDays;
  final List<PriceTrendPoint> points;
  final String trend; // 'increasing' | 'decreasing' | 'stable' | 'insufficient_data'
  final double? changePercent;
  final double? latestPricePerKg;
  final DateTime? latestDate;

  const PriceTrend({
    required this.item,
    this.wardId,
    required this.scope,
    required this.windowDays,
    required this.points,
    required this.trend,
    this.changePercent,
    this.latestPricePerKg,
    this.latestDate,
  });

  /// A chart and direction are only shown when the backend had enough real
  /// history to determine a trend.
  bool get hasTrend => trend != 'insufficient_data' && points.length >= 2;

  int get totalSales => points.fold(0, (sum, p) => sum + p.sales);

  factory PriceTrend.fromJson(Map<String, dynamic> json) => PriceTrend(
        item: json['item'] as String,
        wardId: json['ward_id'] as String?,
        scope: json['scope'] as String? ?? 'ward',
        windowDays: (json['window_days'] as num?)?.toInt() ?? 90,
        points: (json['points'] as List<dynamic>? ?? [])
            .map((p) => PriceTrendPoint.fromJson(p as Map<String, dynamic>))
            .toList(),
        trend: json['trend'] as String? ?? 'insufficient_data',
        changePercent: (json['change_percent'] as num?)?.toDouble(),
        latestPricePerKg: (json['latest_price_per_kg'] as num?)?.toDouble(),
        latestDate: json['latest_date'] == null ? null : DateTime.parse(json['latest_date'] as String),
      );
}
