/// Backing model for both `GET /ewaste/submissions` (full raw document,
/// minus `_id`) and `GET /ewaste/submissions/{id}` (a narrower
/// response_model — submission_id/home_user_id/ward_id/status/home_lat/
/// home_lng/home_ts only). Fields the detail endpoint doesn't return are
/// nullable here rather than assumed present, so both shapes parse safely.
class Submission {
  final String submissionId;
  final String homeUserId;
  final String wardId;
  final String status;
  final double? homeLat;
  final double? homeLng;
  final DateTime? homeTs;
  final String? photoFileId;
  final String? category;
  final String? condition;
  final double? approximateWeightKg;
  final double? actualWeightKg;
  final String? assignedCollectorId;
  final double? collectorLat;
  final double? collectorLng;
  final DateTime? collectionTs;
  final DateTime? createdAt;
  final AiClassification? aiClassification;
  final PriceEstimate? priceEstimate;
  final String? lotId;

  const Submission({
    required this.submissionId,
    required this.homeUserId,
    required this.wardId,
    required this.status,
    this.homeLat,
    this.homeLng,
    this.homeTs,
    this.photoFileId,
    this.category,
    this.condition,
    this.approximateWeightKg,
    this.actualWeightKg,
    this.assignedCollectorId,
    this.collectorLat,
    this.collectorLng,
    this.collectionTs,
    this.createdAt,
    this.aiClassification,
    this.priceEstimate,
    this.lotId,
  });

  factory Submission.fromJson(Map<String, dynamic> json) => Submission(
    submissionId: json['submission_id'] as String,
    homeUserId: json['home_user_id'] as String,
    wardId: json['ward_id'] as String,
    status: json['status'] as String,
    homeLat: (json['home_lat'] as num?)?.toDouble(),
    homeLng: (json['home_lng'] as num?)?.toDouble(),
    homeTs: json['home_ts'] == null
        ? null
        : DateTime.tryParse(json['home_ts'] as String),
    photoFileId: json['photo_file_id'] as String?,
    category: json['category'] as String?,
    condition: json['condition'] as String?,
    approximateWeightKg: (json['approximate_weight_kg'] as num?)?.toDouble(),
    actualWeightKg: (json['actual_weight_kg'] as num?)?.toDouble(),
    assignedCollectorId: json['assigned_collector_id'] as String?,
    collectorLat: (json['collector_lat'] as num?)?.toDouble(),
    collectorLng: (json['collector_lng'] as num?)?.toDouble(),
    collectionTs: json['collection_ts'] == null
        ? null
        : DateTime.tryParse(json['collection_ts'] as String),
    createdAt: json['created_at'] == null
        ? null
        : DateTime.tryParse(json['created_at'] as String),
    aiClassification: json['ai_classification'] == null
      ? null
      : AiClassification.fromJson(
        json['ai_classification'] as Map<String, dynamic>,
        ),
      priceEstimate: json['price_estimate'] == null
        ? null
        : PriceEstimate.fromJson(json['price_estimate'] as Map<String, dynamic>),
      lotId: json['lot_id'] as String?,
  );

  Submission copyWith({String? status, String? assignedCollectorId}) =>
      Submission(
        submissionId: submissionId,
        homeUserId: homeUserId,
        wardId: wardId,
        status: status ?? this.status,
        homeLat: homeLat,
        homeLng: homeLng,
        homeTs: homeTs,
        photoFileId: photoFileId,
        category: category,
        condition: condition,
        approximateWeightKg: approximateWeightKg,
        actualWeightKg: actualWeightKg,
        assignedCollectorId: assignedCollectorId ?? this.assignedCollectorId,
        collectorLat: collectorLat,
        collectorLng: collectorLng,
        collectionTs: collectionTs,
        createdAt: createdAt,
        aiClassification: aiClassification,
        priceEstimate: priceEstimate,
      );
}

class PriceEstimate {
  final double predictedPricePerKg;
  final double minPrice;
  final double maxPrice;
  final double estimatedTotalValue;
  /// Backend-derived total range (min/max price per kg x weight). Null only
  /// for estimates from a backend that predates these fields.
  final double? estimatedTotalMin;
  final double? estimatedTotalMax;
  final String? trend;
  final String productType;
  final String condition;
  final double weightKg;
  final bool isEstimate;
  final String? modelVersion;
  final DateTime? estimatedAt;

  const PriceEstimate({
    required this.predictedPricePerKg,
    required this.minPrice,
    required this.maxPrice,
    required this.estimatedTotalValue,
    this.estimatedTotalMin,
    this.estimatedTotalMax,
    this.trend,
    required this.productType,
    required this.condition,
    required this.weightKg,
    required this.isEstimate,
    this.modelVersion,
    this.estimatedAt,
  });

  factory PriceEstimate.fromJson(Map<String, dynamic> json) => PriceEstimate(
        predictedPricePerKg: (json['predicted_price_per_kg'] as num).toDouble(),
        minPrice: (json['min_price'] as num).toDouble(),
        maxPrice: (json['max_price'] as num).toDouble(),
        estimatedTotalValue: (json['estimated_total_value'] as num).toDouble(),
        estimatedTotalMin: (json['estimated_total_min'] as num?)?.toDouble(),
        estimatedTotalMax: (json['estimated_total_max'] as num?)?.toDouble(),
        trend: json['trend'] as String?,
        productType: json['product_type'] as String,
        condition: json['condition'] as String,
        weightKg: (json['weight_kg'] as num).toDouble(),
        isEstimate: json['is_estimate'] as bool? ?? true,
        modelVersion: json['model_version'] as String?,
        estimatedAt: json['estimated_at'] == null
            ? null
            : DateTime.tryParse(json['estimated_at'] as String),
      );

  Map<String, dynamic> toJson() => {
        'predicted_price_per_kg': predictedPricePerKg,
        'min_price': minPrice,
        'max_price': maxPrice,
        'estimated_total_value': estimatedTotalValue,
        'estimated_total_min': estimatedTotalMin,
        'estimated_total_max': estimatedTotalMax,
        'trend': trend,
        'product_type': productType,
        'condition': condition,
        'weight_kg': weightKg,
        'is_estimate': isEstimate,
        'model_version': modelVersion,
        'estimated_at': estimatedAt?.toUtc().toIso8601String(),
      };

  /// e.g. "₹98.21 – ₹120.03 / kg".
  String get pricePerKgLabel =>
      '₹${minPrice.toStringAsFixed(2)} – ₹${maxPrice.toStringAsFixed(2)} / kg';

  /// e.g. "₹39.28 – ₹48.01" — displays the backend's total range as-is; falls
  /// back to the single legacy total only when the range is absent.
  String get estimatedTotalLabel =>
      estimatedTotalMin != null && estimatedTotalMax != null
          ? '₹${estimatedTotalMin!.toStringAsFixed(2)} – ₹${estimatedTotalMax!.toStringAsFixed(2)}'
          : '₹${estimatedTotalValue.toStringAsFixed(2)}';
}

class AiClassification {
  final String? detectedClass;
  final double? confidence;
  final int objectCount;
  final List<List<double>> boundingBoxes;

  const AiClassification({
    this.detectedClass,
    this.confidence,
    required this.objectCount,
    required this.boundingBoxes,
  });

  factory AiClassification.fromJson(Map<String, dynamic> json) => AiClassification(
    detectedClass: json['detected_class'] as String?,
    confidence: (json['confidence'] as num?)?.toDouble(),
    objectCount: (json['object_count'] as num?)?.toInt() ?? 0,
    boundingBoxes: (json['detections'] as List<dynamic>? ?? [])
        .map(
          (item) => ((item as Map<String, dynamic>)['bounding_box'] as List<dynamic>? ?? [])
              .map((value) => (value as num).toDouble())
              .toList(),
        )
        .toList(),
  );
}

class PhotoClassificationResult {
  final String? category;
  final String? predictedCategory;
  final double? confidence;
  final String? detectedClass;
  final int objectCount;
  final List<List<double>> boundingBoxes;
  final bool needsReview;
  final String? failureReason;

  const PhotoClassificationResult({
    this.category,
    this.predictedCategory,
    this.confidence,
    this.detectedClass,
    required this.objectCount,
    required this.boundingBoxes,
    required this.needsReview,
    this.failureReason,
  });

  /// The YOLO class of the most confident detection (the backend's rule
  /// for choosing the primary object), made readable:
  /// 'TV-Remote-Control' -> 'TV Remote Control'. The class name itself is
  /// not remapped. Null when nothing was detected.
  String? get detectedItemName {
    final name = detectedClass?.replaceAll(RegExp(r'[-_]+'), ' ').trim();
    return name == null || name.isEmpty ? null : name;
  }

  factory PhotoClassificationResult.fromJson(Map<String, dynamic> json) =>
      PhotoClassificationResult(
        category: json['category'] as String?,
        predictedCategory: json['predicted_category'] as String?,
        confidence: (json['confidence'] as num?)?.toDouble(),
        detectedClass: json['detected_class'] as String?,
        objectCount: (json['object_count'] as num?)?.toInt() ?? 0,
        boundingBoxes: (json['bounding_boxes'] as List<dynamic>? ?? [])
            .map((box) => (box as List<dynamic>)
                .map((value) => (value as num).toDouble())
                .toList())
            .toList(),
        needsReview: json['needs_review'] as bool? ?? true,
        failureReason: json['failure_reason'] as String?,
      );
}

/// The direct result of `POST /ewaste/submissions` — just what the
/// backend actually returns for that call, not the full document.
class SubmissionCreateResult {
  final String submissionId;
  final String status;
  final String? assignedCollectorId;

  const SubmissionCreateResult({
    required this.submissionId,
    required this.status,
    this.assignedCollectorId,
  });

  factory SubmissionCreateResult.fromJson(Map<String, dynamic> json) =>
      SubmissionCreateResult(
        submissionId: json['submission_id'] as String,
        status: json['status'] as String,
        assignedCollectorId: json['assigned_collector_id'] as String?,
      );
}
