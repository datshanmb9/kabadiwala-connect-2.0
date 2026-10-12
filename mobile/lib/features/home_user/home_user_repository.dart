import '../../core/api_client.dart';
import 'models/home_user_profile.dart';
import 'models/ward.dart';

class HomeUserRepository {
  final ApiClient apiClient;

  HomeUserRepository({required this.apiClient});

  /// Public endpoint — no token, since the user has no account yet.
  Future<List<Ward>> listWards() async {
    final json = await apiClient.get('/api/v1/wards');
    final wards = (json['wards'] as List<dynamic>? ?? [])
        .map((w) => Ward.fromJson(w as Map<String, dynamic>))
        .toList();
    return wards;
  }

  /// Public endpoint — self-registration. Returns the created profile;
  /// the caller (RegisterController) is responsible for logging in
  /// afterward — registration itself does not return tokens.
  Future<HomeUserProfile> register({
    required String username,
    required String password,
    required String fullName,
    required String address,
    required String wardId,
    required double householdLat,
    required double householdLng,
    String? upiId,
  }) async {
    final json = await apiClient.post(
      '/api/v1/home-users/register',
      body: {
        'username': username,
        'password': password,
        'full_name': fullName,
        'address': address,
        'ward_id': wardId,
        'household_lat': householdLat,
        'household_lng': householdLng,
        if (upiId != null && upiId.isNotEmpty) 'upi_id': upiId,
      },
    );
    return HomeUserProfile.fromJson(json);
  }

  Future<HomeUserProfile> getProfile(String accessToken) async {
    final json = await apiClient.get('/api/v1/home-users/me', token: accessToken);
    return HomeUserProfile.fromJson(json);
  }

  Future<HomeUserProfile> updateProfile({
    required String accessToken,
    required String fullName,
    required String address,
  }) async {
    final json = await apiClient.patch(
      '/api/v1/home-users/me',
      token: accessToken,
      body: {'full_name': fullName, 'address': address},
    );
    return HomeUserProfile.fromJson(json);
  }

  Future<HomeUserProfile> updatePreferences({
    required String accessToken,
    String? language,
    bool? collectionUpdates,
    bool? statusUpdates,
    bool? accountUpdates,
  }) async {
    final json = await apiClient.patch(
      '/api/v1/home-users/me/preferences',
      token: accessToken,
      body: {
        ...?language == null ? null : {'language': language},
        ...?collectionUpdates == null ? null : {'collection_updates': collectionUpdates},
        ...?statusUpdates == null ? null : {'status_updates': statusUpdates},
        ...?accountUpdates == null ? null : {'account_updates': accountUpdates},
      },
    );
    return HomeUserProfile.fromJson(json);
  }

  Future<void> deactivateAccount(String accessToken) async {
    await apiClient.post('/api/v1/home-users/me/deactivate', token: accessToken);
  }
}
