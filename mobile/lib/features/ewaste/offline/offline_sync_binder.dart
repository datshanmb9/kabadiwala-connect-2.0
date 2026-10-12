import 'package:flutter/widgets.dart';
import 'package:provider/provider.dart';

import '../../auth/auth_controller.dart';
import 'offline_submission_sync.dart';

/// Triggers offline-submission sync at the points where a queued item
/// could otherwise get stuck: connectivity restored (via
/// OfflineSubmissionSync.start), a session becoming available (app start /
/// login), and the app returning to the foreground. No polling.
class OfflineSyncBinder extends StatefulWidget {
  final Widget child;

  const OfflineSyncBinder({super.key, required this.child});

  @override
  State<OfflineSyncBinder> createState() => _OfflineSyncBinderState();
}

class _OfflineSyncBinderState extends State<OfflineSyncBinder> with WidgetsBindingObserver {
  late final OfflineSubmissionSync _sync;
  late final AuthController _auth;
  String? _syncedForUserId;

  @override
  void initState() {
    super.initState();
    _sync = context.read<OfflineSubmissionSync>();
    _auth = context.read<AuthController>();
    WidgetsBinding.instance.addObserver(this);
    _auth.addListener(_onAuthChanged);
    _sync.start();
    _onAuthChanged();
  }

  void _onAuthChanged() {
    final userId = _auth.isAuthenticated ? _auth.session!.userId : null;
    if (userId != null && userId != _syncedForUserId) _sync.syncPending();
    _syncedForUserId = userId;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _sync.syncPending();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _auth.removeListener(_onAuthChanged);
    _sync.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
