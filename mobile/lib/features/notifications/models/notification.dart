class AppNotification {
  final String notificationId;
  final String type;
  final String titleKey;
  final String messageKey;
  final String? relatedEntityType;
  final String? relatedEntityId;
  final bool read;
  final DateTime createdAt;
  final DateTime? readAt;
  final Map<String, dynamic> metadata;

  const AppNotification({
    required this.notificationId,
    required this.type,
    required this.titleKey,
    required this.messageKey,
    required this.relatedEntityType,
    required this.relatedEntityId,
    required this.read,
    required this.createdAt,
    required this.readAt,
    required this.metadata,
  });

  factory AppNotification.fromJson(Map<String, dynamic> json) => AppNotification(
        notificationId: json['notification_id'] as String,
        type: json['type'] as String,
        titleKey: json['title_key'] as String,
        messageKey: json['message_key'] as String,
        relatedEntityType: json['related_entity_type'] as String?,
        relatedEntityId: json['related_entity_id'] as String?,
        read: json['read'] as bool? ?? false,
        createdAt: DateTime.parse(json['created_at'] as String),
        readAt: json['read_at'] == null
            ? null
            : DateTime.parse(json['read_at'] as String),
        metadata: Map<String, dynamic>.from(json['metadata'] as Map? ?? const {}),
      );

  AppNotification copyWith({bool? read, DateTime? readAt}) => AppNotification(
        notificationId: notificationId,
        type: type,
        titleKey: titleKey,
        messageKey: messageKey,
        relatedEntityType: relatedEntityType,
        relatedEntityId: relatedEntityId,
        read: read ?? this.read,
        createdAt: createdAt,
        readAt: readAt ?? this.readAt,
        metadata: metadata,
      );
}

class NotificationPage {
  final List<AppNotification> notifications;
  final int unreadCount;
  final bool hasMore;

  const NotificationPage({
    required this.notifications,
    required this.unreadCount,
    required this.hasMore,
  });

  factory NotificationPage.fromJson(Map<String, dynamic> json) => NotificationPage(
        notifications: (json['notifications'] as List<dynamic>? ?? [])
            .map((item) => AppNotification.fromJson(item as Map<String, dynamic>))
            .toList(),
        unreadCount: json['unread_count'] as int? ?? 0,
        hasMore: json['has_more'] as bool? ?? false,
      );
}
