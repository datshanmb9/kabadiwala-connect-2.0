/// A home user's e-waste submission saved on the device because the
/// network was unavailable when they pressed Submit. Holds everything the
/// normal online flow sends (see EwasteRepository.createSubmission), plus
/// the SAME idempotency key the screen generated for that attempt, so every
/// sync retry is a replay of one request — never a new submission.
class OfflineSubmission {
  final String localId;
  final String userId;
  final String idempotencyKey;
  final String wardId;
  final double homeLat;
  final double homeLng;
  final String? category;
  final String? condition;
  final double? approximateWeightKg;
  final Map<String, dynamic>? priceEstimate;

  /// File name of the persisted photo inside this record's own directory.
  final String photoFileName;

  /// Set once the photo upload has succeeded, so a retry after a failed
  /// create call doesn't upload the same photo again.
  final String? photoFileId;
  final DateTime createdAt;
  final int attempts;
  final String? lastError;

  const OfflineSubmission({
    required this.localId,
    required this.userId,
    required this.idempotencyKey,
    required this.wardId,
    required this.homeLat,
    required this.homeLng,
    this.category,
    this.condition,
    this.approximateWeightKg,
    this.priceEstimate,
    required this.photoFileName,
    this.photoFileId,
    required this.createdAt,
    this.attempts = 0,
    this.lastError,
  });

  OfflineSubmission copyWith({String? photoFileId, int? attempts, String? lastError}) => OfflineSubmission(
        localId: localId,
        userId: userId,
        idempotencyKey: idempotencyKey,
        wardId: wardId,
        homeLat: homeLat,
        homeLng: homeLng,
        category: category,
        condition: condition,
        approximateWeightKg: approximateWeightKg,
        priceEstimate: priceEstimate,
        photoFileName: photoFileName,
        photoFileId: photoFileId ?? this.photoFileId,
        createdAt: createdAt,
        attempts: attempts ?? this.attempts,
        lastError: lastError ?? this.lastError,
      );

  factory OfflineSubmission.fromJson(Map<String, dynamic> json) => OfflineSubmission(
        localId: json['local_id'] as String,
        userId: json['user_id'] as String,
        idempotencyKey: json['idempotency_key'] as String,
        wardId: json['ward_id'] as String,
        homeLat: (json['home_lat'] as num).toDouble(),
        homeLng: (json['home_lng'] as num).toDouble(),
        category: json['category'] as String?,
        condition: json['condition'] as String?,
        approximateWeightKg: (json['approximate_weight_kg'] as num?)?.toDouble(),
        priceEstimate: json['price_estimate'] == null
            ? null
            : Map<String, dynamic>.from(json['price_estimate'] as Map),
        photoFileName: json['photo_file_name'] as String,
        photoFileId: json['photo_file_id'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        attempts: json['attempts'] as int? ?? 0,
        lastError: json['last_error'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'local_id': localId,
        'user_id': userId,
        'idempotency_key': idempotencyKey,
        'ward_id': wardId,
        'home_lat': homeLat,
        'home_lng': homeLng,
        'category': category,
        'condition': condition,
        'approximate_weight_kg': approximateWeightKg,
        'price_estimate': priceEstimate,
        'photo_file_name': photoFileName,
        'photo_file_id': photoFileId,
        'created_at': createdAt.toUtc().toIso8601String(),
        'attempts': attempts,
        'last_error': lastError,
      };
}
