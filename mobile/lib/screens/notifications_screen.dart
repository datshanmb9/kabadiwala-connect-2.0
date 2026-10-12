import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exception.dart';
import '../features/auth/auth_controller.dart';
import '../features/notifications/models/notification.dart';
import '../features/notifications/notifications_repository.dart';
import '../features/translation/translation_text.dart';
import '../shared/state_views.dart';
import 'submission_detail_screen.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  static const _pageSize = 20;
  final _notifications = <AppNotification>[];
  final _markingRead = <String>{};
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasMore = false;
  int _unreadCount = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load(refresh: true);
  }

  Future<void> _load({required bool refresh}) async {
    if (refresh) {
      setState(() {
        _loading = true;
        _error = null;
      });
    } else {
      if (_loadingMore || !_hasMore) return;
      setState(() => _loadingMore = true);
    }
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      final page = await context.read<NotificationsRepository>().listNotifications(
        accessToken: token,
        limit: _pageSize,
        offset: refresh ? 0 : _notifications.length,
      );
      if (!mounted) return;
      setState(() {
        if (refresh) _notifications.clear();
        _notifications.addAll(page.notifications);
        _unreadCount = page.unreadCount;
        _hasMore = page.hasMore;
        _loading = false;
        _loadingMore = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = context.tr('Could not reach the server. Check your connection and try again.');
        _loading = false;
        _loadingMore = false;
      });
    }
  }

  Future<void> _markRead(AppNotification notification) async {
    if (notification.read || _markingRead.contains(notification.notificationId)) return;
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    setState(() => _markingRead.add(notification.notificationId));
    try {
      final updated = await context.read<NotificationsRepository>().markRead(
        accessToken: token,
        notificationId: notification.notificationId,
      );
      if (!mounted) return;
      final index = _notifications.indexWhere(
        (item) => item.notificationId == updated.notificationId,
      );
      if (index >= 0) {
        setState(() {
          _notifications[index] = updated;
          if (_unreadCount > 0) _unreadCount--;
        });
      }
    } on ApiException catch (e) {
      if (mounted) _showError(e.message);
    } catch (_) {
      if (mounted) _showError(context.tr('Notification could not be updated.'));
    } finally {
      if (mounted) setState(() => _markingRead.remove(notification.notificationId));
    }
  }

  Future<void> _markAllRead() async {
    if (_unreadCount == 0) return;
    final token = context.read<AuthController>().session?.accessToken;
    if (token == null) return;
    try {
      await context.read<NotificationsRepository>().markAllRead(token);
      if (!mounted) return;
      setState(() {
        for (var index = 0; index < _notifications.length; index++) {
          _notifications[index] = _notifications[index].copyWith(read: true);
        }
        _unreadCount = 0;
      });
    } on ApiException catch (e) {
      if (mounted) _showError(e.message);
    } catch (_) {
      if (mounted) _showError(context.tr('Notification could not be updated.'));
    }
  }

  Future<void> _open(AppNotification notification) async {
    await _markRead(notification);
    if (!mounted) return;
    if (notification.relatedEntityType == 'e_waste_submission' &&
        notification.relatedEntityId != null) {
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => SubmissionDetailScreen(
            submissionId: notification.relatedEntityId!,
          ),
        ),
      );
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.tr(message))));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(context.tr('Notifications')),
        actions: [
          if (_unreadCount > 0)
            TextButton(
              key: const Key('mark_all_notifications_read_button'),
              onPressed: _markAllRead,
              child: Text(context.tr('Mark all as read')),
            ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) return LoadingView(message: context.tr('Loading notifications...'));
    if (_error != null && _notifications.isEmpty) {
      return ErrorView(message: _error!, onRetry: () => _load(refresh: true));
    }
    if (_notifications.isEmpty) {
      return RefreshIndicator(
        onRefresh: () => _load(refresh: true),
        child: ListView(
          children: [
            const SizedBox(height: 120),
            EmptyView(message: context.tr('No notifications yet.'), icon: Icons.notifications_none),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: () => _load(refresh: true),
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _notifications.length + (_hasMore ? 1 : 0),
        itemBuilder: (context, index) {
          if (index == _notifications.length) {
            if (!_loadingMore) _load(refresh: false);
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          final notification = _notifications[index];
          return _NotificationTile(
            notification: notification,
            relativeTime: _relativeTime(notification.createdAt),
            onTap: () => _open(notification),
          );
        },
      ),
    );
  }

  String _relativeTime(DateTime createdAt) {
    final difference = DateTime.now().toUtc().difference(createdAt.toUtc());
    if (difference.inMinutes < 1) return context.tr('Just now');
    if (difference.inHours < 1) return context.trf('{count} min ago', {'count': difference.inMinutes});
    if (difference.inHours < 24) return context.trf('{count} h ago', {'count': difference.inHours});
    if (difference.inDays == 1) return context.tr('Yesterday');
    return context.trf('{count} days ago', {'count': difference.inDays});
  }
}

class _NotificationTile extends StatelessWidget {
  final AppNotification notification;
  final String relativeTime;
  final VoidCallback onTap;

  const _NotificationTile({
    required this.notification,
    required this.relativeTime,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      key: Key('notification_${notification.notificationId}'),
      leading: Icon(
        notification.read ? Icons.done : Icons.notifications_active_outlined,
        color: notification.read ? Colors.grey : Theme.of(context).colorScheme.primary,
      ),
      title: Text(
        context.tr(notification.titleKey),
        style: TextStyle(fontWeight: notification.read ? FontWeight.normal : FontWeight.bold),
      ),
      subtitle: Text('${context.tr(notification.messageKey)}\n$relativeTime'),
      isThreeLine: true,
      trailing: notification.read
          ? null
          : const Icon(Icons.circle, size: 10),
      tileColor: notification.read ? null : Theme.of(context).colorScheme.primary.withAlpha(12),
      onTap: onTap,
    );
  }
}
