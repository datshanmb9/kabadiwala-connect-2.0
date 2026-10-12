import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kabadiwala_mobile/core/api_client.dart';
import 'package:kabadiwala_mobile/core/auth_storage.dart';
import 'package:kabadiwala_mobile/features/auth/auth_controller.dart';
import 'package:kabadiwala_mobile/features/auth/auth_repository.dart';
import 'package:kabadiwala_mobile/features/auth/models/auth_session.dart';
import 'package:kabadiwala_mobile/features/notifications/models/notification.dart';
import 'package:kabadiwala_mobile/features/notifications/notifications_repository.dart';
import 'package:kabadiwala_mobile/screens/notifications_screen.dart';
import 'package:provider/provider.dart';

http.Response _json(Map<String, dynamic> body, int status) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

Map<String, dynamic> _notification({bool read = false}) => {
      'notification_id': 'notification-1',
      'type': 'COLLECTION_REQUEST_CREATED',
      'title_key': 'Collection request created',
      'message_key': 'Your e-waste submission was successfully received.',
      'related_entity_type': 'e_waste_submission',
      'related_entity_id': 'submission-1',
      'read': read,
      'created_at': DateTime.now().toUtc().toIso8601String(),
      'read_at': read ? DateTime.now().toUtc().toIso8601String() : null,
      'metadata': {'status': 'WAITING_FOR_COLLECTION'},
    };

AuthController _authController() {
  final auth = AuthController(
    repository: AuthRepository(
      apiClient: ApiClient(
        baseUrl: 'http://test',
        client: MockClient((_) async => _json({}, 200)),
      ),
      authStorage: AuthStorage(),
    ),
  );
  auth.session = const AuthSession(
    accessToken: 'token',
    refreshToken: 'refresh',
    role: 'HOME_USER',
    userId: 'user-1',
    username: 'citizen1',
  );
  auth.status = AuthStatus.authenticated;
  return auth;
}

Widget _screenWith(http.Client client) {
  return MultiProvider(
    providers: [
      Provider<NotificationsRepository>(
        create: (_) => NotificationsRepository(
          apiClient: ApiClient(baseUrl: 'http://test', client: client),
        ),
      ),
      ChangeNotifierProvider<AuthController>.value(value: _authController()),
    ],
    child: const MaterialApp(home: NotificationsScreen()),
  );
}

void main() {
  test('parses stable notification keys and metadata', () {
    final notification = AppNotification.fromJson(_notification());
    expect(notification.type, 'COLLECTION_REQUEST_CREATED');
    expect(notification.titleKey, 'Collection request created');
    expect(notification.metadata['status'], 'WAITING_FOR_COLLECTION');
  });

  test('repository sends authenticated list and read-all requests', () async {
    final paths = <String>[];
    final repository = NotificationsRepository(
      apiClient: ApiClient(
        baseUrl: 'http://test',
        client: MockClient((request) async {
          paths.add(request.url.path);
          if (request.url.path.endsWith('/read-all')) {
            return _json({'marked_count': 1, 'unread_count': 0}, 200);
          }
          return _json({
            'notifications': [_notification()],
            'unread_count': 1,
            'has_more': false,
          }, 200);
        }),
      ),
    );
    final page = await repository.listNotifications(accessToken: 'token');
    final marked = await repository.markAllRead('token');
    expect(page.notifications, hasLength(1));
    expect(page.unreadCount, 1);
    expect(marked, 1);
    expect(paths, ['/api/v1/notifications', '/api/v1/notifications/read-all']);
  });

  testWidgets('shows empty notification state', (tester) async {
    await tester.pumpWidget(_screenWith(
      MockClient((_) async => _json({
        'notifications': [],
        'unread_count': 0,
        'has_more': false,
      }, 200)),
    ));
    await tester.pumpAndSettle();
    expect(find.text('No notifications yet.'), findsOneWidget);
  });

  testWidgets('shows unread notification and mark-all action', (tester) async {
    await tester.pumpWidget(_screenWith(
      MockClient((request) async {
        if (request.url.path.endsWith('/read-all')) {
          return _json({'marked_count': 1, 'unread_count': 0}, 200);
        }
        return _json({
          'notifications': [_notification()],
          'unread_count': 1,
          'has_more': false,
        }, 200);
      }),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Collection request created'), findsOneWidget);
    expect(find.byKey(const Key('mark_all_notifications_read_button')), findsOneWidget);
    await tester.tap(find.byKey(const Key('mark_all_notifications_read_button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('mark_all_notifications_read_button')), findsNothing);
  });
}
