
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api_client.dart';
import '../pricing/price_trend.dart';
import 'models/handover_result.dart';
import 'models/submission.dart';

class EwasteRepository {
  final ApiClient apiClient;

  EwasteRepository({required this.apiClient});

  Future<String> uploadPhoto({
    required String accessToken,
    required XFile file,
  }) async {
    final fileName = file.name.toLowerCase();

    String? contentType = file.mimeType;

    // Infer MIME type from filename if it is missing or unsupported.
    if (contentType != 'image/jpeg' &&
        contentType != 'image/png' &&
        contentType != 'image/webp') {
      if (fileName.endsWith('.jpg') || fileName.endsWith('.jpeg')) {
        contentType = 'image/jpeg';
      } else if (fileName.endsWith('.png')) {
        contentType = 'image/png';
      } else if (fileName.endsWith('.webp')) {
        contentType = 'image/webp';
      } else {
        throw ArgumentError(
          'Only JPEG, PNG and WEBP images are supported.',
        );
      }
    }

    final response = await apiClient.postMultipart(
      '/api/v1/ewaste/photos',
      token: accessToken,
      file: http.MultipartFile(
        'file',
        file.openRead(),
        await file.length(),
        filename: file.name,
        contentType: MediaType.parse(contentType!),
      ),
    );

    return response['photo_file_id'] as String;
  }

  Future<PhotoClassificationResult> classifyPhoto({
    required String accessToken,
    required String photoFileId,
  }) async {
    final json = await apiClient.post(
      '/api/v1/ai/classify-photo',
      token: accessToken,
      body: {'photo_file_id': photoFileId},
    );
    return PhotoClassificationResult.fromJson(json);
  }

  Future<SubmissionCreateResult> createSubmission({
    required String accessToken,
    required String wardId,
    required String photoFileId,
    required double homeLat,
    required double homeLng,
    String? category,
    String? condition,
    double? approximateWeightKg,
    PriceEstimate? priceEstimate,
    required String idempotencyKey,
  }) async {
    final body = <String, dynamic>{
      'ward_id': wardId,
      'photo_file_id': photoFileId,
      'home_lat': homeLat,
      'home_lng': homeLng,
    };
    if (category != null) body['category'] = category;
    if (condition != null) body['condition'] = condition;
    if (approximateWeightKg != null) {
      body['approximate_weight_kg'] = approximateWeightKg;
    }
    if (priceEstimate != null) body['price_estimate'] = priceEstimate.toJson();

    final json = await apiClient.post(
      '/api/v1/ewaste/submissions',
      token: accessToken,
      idempotencyKey: idempotencyKey,
      body: body,
    );

    return SubmissionCreateResult.fromJson(json);
  }

  Future<PriceEstimate> estimatePrice({
    required String accessToken,
    required String productType,
    required String condition,
    required double weightKg,
    required String location,
  }) async {
    final json = await apiClient.post(
      '/api/v1/pricing/estimate',
      token: accessToken,
      body: {
        'product_type': productType,
        'condition': condition,
        'quantity': 1,
        'total_weight_kg': weightKg,
        'location': location,
      },
    );
    return PriceEstimate.fromJson(json);
  }

  /// Historical price trend for [item] (ward first, then all wards), shared
  /// by the Home User and Collector screens.
  Future<PriceTrend> getPriceTrend({
    required String accessToken,
    required String item,
    String? wardId,
  }) async {
    final query = Uri(queryParameters: {
      'item': item,
      if (wardId != null && wardId.isNotEmpty) 'ward_id': wardId,
    }).query;
    final json = await apiClient.get('/api/v1/pricing/trend?$query', token: accessToken);
    return PriceTrend.fromJson(json);
  }

  Future<List<Submission>> listSubmissions(String accessToken) async {
    final json = await apiClient.get(
      '/api/v1/ewaste/submissions',
      token: accessToken,
    );

    return (json['submissions'] as List<dynamic>? ?? [])
        .map((s) => Submission.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  Future<Submission> getSubmission(
    String submissionId,
    String accessToken,
  ) async {
    final json = await apiClient.get(
      '/api/v1/ewaste/submissions/$submissionId',
      token: accessToken,
    );

    return Submission.fromJson(json);
  }

  /// Collector-only: submissions awaiting collection in the caller's own
  /// ward. The backend derives the ward from the collector's own profile
  /// server-side — this call never sends a ward filter.
  Future<List<Submission>> listPendingForCollector(
    String accessToken,
  ) async {
    final json = await apiClient.get(
      '/api/v1/ewaste/submissions/pending',
      token: accessToken,
    );

    return (json['submissions'] as List<dynamic>? ?? [])
        .map((s) => Submission.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  Future<List<Submission>> listAssignedForCollector(
    String accessToken,
  ) async {
    final json = await apiClient.get(
      '/api/v1/ewaste/submissions/assigned',
      token: accessToken,
    );

    return (json['submissions'] as List<dynamic>? ?? [])
        .map((s) => Submission.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  /// "Accepted Collections": submissions this collector has already handed
  /// over (status COLLECTED or later) — distinct from
  /// [listAssignedForCollector] above, which is the pre-handover queue of
  /// items still awaiting physical pickup.
  Future<List<Submission>> listHandedOverForCollector(
    String accessToken,
  ) async {
    final json = await apiClient.get(
      '/api/v1/ewaste/submissions/handed-over',
      token: accessToken,
    );

    return (json['submissions'] as List<dynamic>? ?? [])
        .map((s) => Submission.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  Future<SubmissionCreateResult> acceptSubmission({
    required String accessToken,
    required String submissionId,
    required String idempotencyKey,
  }) async {
    final json = await apiClient.post(
      '/api/v1/ewaste/submissions/$submissionId/accept',
      token: accessToken,
      idempotencyKey: idempotencyKey,
    );

    return SubmissionCreateResult.fromJson(json);
  }

  /// Collector-only: confirms handover for a submission, with the
  /// collector's live-captured photo reference and GPS. The returned
  /// verification result/status are exactly what the backend computed —
  /// this call never assumes success.
  Future<HandoverResult> handover({
    required String accessToken,
    required String submissionId,
    required String photoFileId,
    required double collectorLat,
    required double collectorLng,
    double? actualWeightKg,
    required String idempotencyKey,
  }) async {
    final json = await apiClient.post(
      '/api/v1/ewaste/submissions/$submissionId/handover',
      token: accessToken,
      idempotencyKey: idempotencyKey,
      body: {
        'photo_file_id': photoFileId,
        'collector_lat': collectorLat,
        'collector_lng': collectorLng,
        if (actualWeightKg != null)
          'actual_weight_kg': actualWeightKg,
      },
    );

    return HandoverResult.fromJson(json);
  }
}