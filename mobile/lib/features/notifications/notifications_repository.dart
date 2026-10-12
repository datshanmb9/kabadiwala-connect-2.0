import '../../core/api_client.dart';
import 'models/notification.dart';

class NotificationsRepository {
  final ApiClient apiClient;

  NotificationsRepository({required this.apiClient});

  Future<NotificationPage> listNotifications({
    required String accessToken,
    int limit = 20,
    int offset = 0,
  }) async {
    final json = await apiClient.get(
      '/api/v1/notifications?limit=$limit&offset=$offset',
      token: accessToken,
    );
    return NotificationPage.fromJson(json);
  }

  Future<int> unreadCount(String accessToken) async {
    final json = await apiClient.get(
      '/api/v1/notifications/unread-count',
      token: accessToken,
    );
    return json['unread_count'] as int? ?? 0;
  }

  Future<AppNotification> markRead({
    required String accessToken,
    required String notificationId,
  }) async {
    final json = await apiClient.patch(
      '/api/v1/notifications/$notificationId/read',
      token: accessToken,
    );
    return AppNotification.fromJson(json);
  }

  Future<int> markAllRead(String accessToken) async {
    final json = await apiClient.patch(
      '/api/v1/notifications/read-all',
      token: accessToken,
    );
    return json['marked_count'] as int? ?? 0;
  }
}
