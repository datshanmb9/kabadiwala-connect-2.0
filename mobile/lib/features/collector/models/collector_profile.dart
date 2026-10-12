/// Mirrors the backend's CollectorProfileResponse exactly. Read-only by
/// construction on both sides — there is no update path exposed to a
/// collector, on the backend or in this app.
class CollectorProfile {
  final String userId;
  final String employeeId;
  final String wardId;
  final String? rrrId;
  final double? assignedAreaRadiusM;

  const CollectorProfile({
    required this.userId,
    required this.employeeId,
    required this.wardId,
    this.rrrId,
    this.assignedAreaRadiusM,
  });

  factory CollectorProfile.fromJson(Map<String, dynamic> json) => CollectorProfile(
        userId: json['user_id'] as String,
        employeeId: json['employee_id'] as String,
        wardId: json['ward_id'] as String,
        rrrId: json['rrr_id'] as String?,
        assignedAreaRadiusM: (json['assigned_area_radius_m'] as num?)?.toDouble(),
      );
}
