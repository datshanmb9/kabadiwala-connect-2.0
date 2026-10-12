/// The real result of `POST /ewaste/submissions/{id}/handover` — mirrors
/// the backend's HandoverResponse exactly. `verificationResult` and
/// `status` are always the backend's actual returned values; this app
/// never fabricates a "VERIFIED"/"COLLECTED" outcome client-side.
class HandoverResult {
  final String submissionId;
  final String status;
  final String verificationResult;
  final double? distanceM;
  final List<String> reasons;
  // Set only when the handover was VERIFIED and the item was successfully
  // auto-listed for bidding (backend's auto_progress_to_listed_lot) — null
  // for a FLAGGED handover, or if the submission had no category on record.
  final String? lotId;
  final String? lotStatus;

  const HandoverResult({
    required this.submissionId,
    required this.status,
    required this.verificationResult,
    this.distanceM,
    this.reasons = const [],
    this.lotId,
    this.lotStatus,
  });

  bool get isVerified => verificationResult == 'VERIFIED';

  factory HandoverResult.fromJson(Map<String, dynamic> json) => HandoverResult(
        submissionId: json['submission_id'] as String,
        status: json['status'] as String,
        verificationResult: json['verification_result'] as String,
        distanceM: (json['distance_m'] as num?)?.toDouble(),
        reasons: (json['reasons'] as List<dynamic>? ?? []).map((r) => r as String).toList(),
        lotId: json['lot_id'] as String?,
        lotStatus: json['lot_status'] as String?,
      );
}
