import '../../core/api_client.dart';
import 'models/collector_profile.dart';

class CollectorRepository {
  final ApiClient apiClient;

  CollectorRepository({required this.apiClient});

  Future<CollectorProfile> getProfile(String accessToken) async {
    final json = await apiClient.get('/api/v1/collectors/me', token: accessToken);
    return CollectorProfile.fromJson(json);
  }
}
