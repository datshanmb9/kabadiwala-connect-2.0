class HomeUserProfile {
  final String userId;
  final String username;
  final String fullName;
  final String address;
  final String wardId;
  final double householdLat;
  final double householdLng;
  final String? upiId;
  final String accountStatus;
  final DateTime? createdAt;
  final Map<String, dynamic> preferences;

  const HomeUserProfile({
    required this.userId,
    required this.username,
    required this.fullName,
    required this.address,
    required this.wardId,
    required this.householdLat,
    required this.householdLng,
    this.upiId,
    this.accountStatus = 'ACTIVE',
    this.createdAt,
    this.preferences = const {},
  });

  factory HomeUserProfile.fromJson(Map<String, dynamic> json) => HomeUserProfile(
        userId: json['user_id'] as String,
        username: json['username'] as String,
        fullName: json['full_name'] as String,
        address: json['address'] as String,
        wardId: json['ward_id'] as String,
        householdLat: (json['household_lat'] as num).toDouble(),
        householdLng: (json['household_lng'] as num).toDouble(),
        upiId: json['upi_id'] as String?,
        accountStatus: json['account_status'] as String? ?? 'ACTIVE',
        createdAt: json['created_at'] == null
            ? null
            : DateTime.tryParse(json['created_at'] as String),
        preferences: Map<String, dynamic>.from(
          json['preferences'] as Map? ?? const {},
        ),
      );
}
