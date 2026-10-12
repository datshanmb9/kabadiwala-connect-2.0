import 'dart:async';
import 'dart:typed_data';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:image_picker/image_picker.dart';
import 'package:uuid/uuid.dart';

import '../../../core/api_exception.dart';
import '../../auth/models/auth_session.dart';
import '../ewaste_repository.dart';
import '../models/submission.dart';
import 'offline_submission.dart';
import 'offline_submission_store.dart';

const offlineSavedMessage =
    "You're offline. Your submission has been saved and will be sent automatically when you're back online.";
const offlineSyncedMessage = 'Your e-waste submission has been sent to the collector.';

/// True for failures where the request may never have reached the server
/// (or its answer never came back) — the cases that queue a submission
/// instead of showing an error.
bool isNetworkFailure(ApiException e) => e.errorCode == 'NETWORK_ERROR' || e.errorCode == 'NETWORK_TIMEOUT';

/// Sends queued offline submissions through the normal online flow
/// (EwasteRepository.uploadPhoto + createSubmission). Each queued item
/// always replays its own stored idempotency key, so the backend returns
/// the original submission instead of creating a second one, however many
/// times a sync is retried. The local copy is removed only after the
/// backend has confirmed the submission.
class OfflineSubmissionSync {
  static const _uuid = Uuid();

  final OfflineSubmissionStore store;
  final EwasteRepository repository;
  final AuthSession? Function() currentSession;

  /// Returns a fresh access token, or null if the session can't be renewed
  /// (the item then simply stays queued until the user logs in again).
  final Future<String?> Function() refreshAccessToken;
  final void Function(SubmissionCreateResult result)? onSynced;
  final Stream<List<ConnectivityResult>> Function()? connectivityChanges;

  StreamSubscription<List<ConnectivityResult>>? _connectivitySub;
  Future<void>? _running;
  bool _rerunRequested = false;

  OfflineSubmissionSync({
    required this.store,
    required this.repository,
    required this.currentSession,
    required this.refreshAccessToken,
    this.onSynced,
    this.connectivityChanges,
  });

  /// Listens for connectivity being restored (event-driven, no polling).
  void start() {
    _connectivitySub ??= (connectivityChanges ?? () => Connectivity().onConnectivityChanged)().listen((results) {
      if (results.any((r) => r != ConnectivityResult.none)) syncPending();
    });
  }

  void dispose() {
    _connectivitySub?.cancel();
    _connectivitySub = null;
  }

  Future<OfflineSubmission> enqueue({
    required String userId,
    required String idempotencyKey,
    required String wardId,
    required double homeLat,
    required double homeLng,
    String? category,
    String? condition,
    double? approximateWeightKg,
    PriceEstimate? priceEstimate,
    required Uint8List photoBytes,
    required String photoName,
    String? photoMimeType,
    String? photoFileId,
  }) async {
    final submission = OfflineSubmission(
      localId: _uuid.v4(),
      userId: userId,
      idempotencyKey: idempotencyKey,
      wardId: wardId,
      homeLat: homeLat,
      homeLng: homeLng,
      category: category,
      condition: condition,
      approximateWeightKg: approximateWeightKg,
      priceEstimate: priceEstimate?.toJson(),
      photoFileName: 'photo${_photoExtension(photoName, photoMimeType)}',
      photoFileId: photoFileId,
      createdAt: DateTime.now().toUtc(),
    );
    await store.save(submission, photoBytes: photoBytes);
    return submission;
  }

  Future<List<OfflineSubmission>> pending() => store.list();

  /// Safe to call from any trigger (connectivity, app start, resume): runs
  /// at most one pass at a time; a call during a pass schedules one more.
  Future<void> syncPending() {
    if (_running != null) {
      _rerunRequested = true;
      return _running!;
    }
    final run = _drain();
    _running = run;
    return run.whenComplete(() => _running = null);
  }

  Future<void> _drain() async {
    do {
      _rerunRequested = false;
      try {
        await _syncAll();
      } catch (_) {
        // Unexpected (e.g. file-system) failure: nothing was removed from
        // the queue, so the next trigger simply retries.
      }
    } while (_rerunRequested);
  }

  Future<void> _syncAll() async {
    final session = currentSession();
    if (session == null || session.role != 'HOME_USER') return;
    String? token = session.accessToken;
    var refreshed = false;

    for (final queued in await store.list()) {
      if (queued.userId != session.userId) continue;
      var item = queued;
      while (true) {
        try {
          if (item.photoFileId == null) {
            final photo = await store.photoFile(item);
            final photoFileId = await repository.uploadPhoto(accessToken: token!, file: XFile(photo.path));
            item = item.copyWith(photoFileId: photoFileId);
            await store.update(item);
          }
          final result = await repository.createSubmission(
            accessToken: token!,
            wardId: item.wardId,
            photoFileId: item.photoFileId!,
            homeLat: item.homeLat,
            homeLng: item.homeLng,
            category: item.category,
            condition: item.condition,
            approximateWeightKg: item.approximateWeightKg,
            priceEstimate: item.priceEstimate == null ? null : PriceEstimate.fromJson(item.priceEstimate!),
            idempotencyKey: item.idempotencyKey,
          );
          await store.remove(item.localId);
          onSynced?.call(result);
          break;
        } on ApiException catch (e) {
          if (e.isInvalidToken && !refreshed) {
            refreshed = true;
            token = await refreshAccessToken();
            if (token != null) continue;
          }
          await store.update(item.copyWith(attempts: item.attempts + 1, lastError: e.errorCode));
          // Offline again, or no usable session: stop this pass; the item
          // stays queued for the next trigger.
          if (isNetworkFailure(e) || token == null || e.isInvalidToken) return;
          break;
        }
      }
    }
  }

  static String _photoExtension(String name, String? mimeType) {
    final lower = name.toLowerCase();
    if (mimeType == 'image/png' || lower.endsWith('.png')) return '.png';
    if (mimeType == 'image/webp' || lower.endsWith('.webp')) return '.webp';
    return '.jpg';
  }
}
