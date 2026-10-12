import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

import 'offline_submission.dart';

/// Persistent on-device queue of [OfflineSubmission]s. One directory per
/// queued submission under the app's private documents directory:
///
/// `offline_submissions/{localId}/photo.{ext}` and
/// `offline_submissions/{localId}/record.json`.
///
/// The photo is written first and record.json last (via temp file + rename),
/// so a record only exists once its photo is safely on disk — a crash
/// mid-save leaves no half-written entry. Nothing depends on the picker's
/// temporary XFile path.
class OfflineSubmissionStore {
  static const _recordFile = 'record.json';

  final Future<Directory> Function() _baseDirectory;

  OfflineSubmissionStore({Future<Directory> Function()? baseDirectory})
      : _baseDirectory = baseDirectory ?? getApplicationDocumentsDirectory;

  Future<Directory> _root() async {
    final dir = Directory('${(await _baseDirectory()).path}${Platform.pathSeparator}offline_submissions');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  Future<Directory> _dirFor(String localId) async =>
      Directory('${(await _root()).path}${Platform.pathSeparator}$localId');

  Future<void> save(OfflineSubmission submission, {required Uint8List photoBytes}) async {
    final dir = await _dirFor(submission.localId);
    await dir.create(recursive: true);
    await File('${dir.path}${Platform.pathSeparator}${submission.photoFileName}').writeAsBytes(photoBytes, flush: true);
    await _writeRecord(dir, submission);
  }

  /// Rewrites only the record (e.g. to remember a photo_file_id after a
  /// successful upload); the photo is left untouched.
  Future<void> update(OfflineSubmission submission) async {
    final dir = await _dirFor(submission.localId);
    if (!await dir.exists()) return;
    await _writeRecord(dir, submission);
  }

  Future<void> _writeRecord(Directory dir, OfflineSubmission submission) async {
    final tmp = File('${dir.path}${Platform.pathSeparator}$_recordFile.tmp');
    await tmp.writeAsString(jsonEncode(submission.toJson()), flush: true);
    await tmp.rename('${dir.path}${Platform.pathSeparator}$_recordFile');
  }

  /// Oldest first. Entries without a readable record or photo are skipped
  /// (never deleted here — a skipped entry is left for inspection rather
  /// than silently lost).
  Future<List<OfflineSubmission>> list() async {
    final root = await _root();
    final result = <OfflineSubmission>[];
    await for (final entity in root.list()) {
      if (entity is! Directory) continue;
      final record = File('${entity.path}${Platform.pathSeparator}$_recordFile');
      if (!await record.exists()) continue;
      try {
        final submission = OfflineSubmission.fromJson(
          jsonDecode(await record.readAsString()) as Map<String, dynamic>,
        );
        if (await photoFile(submission).then((f) => f.exists())) result.add(submission);
      } catch (_) {
        continue;
      }
    }
    result.sort((a, b) => a.createdAt.compareTo(b.createdAt));
    return result;
  }

  Future<File> photoFile(OfflineSubmission submission) async =>
      File('${(await _dirFor(submission.localId)).path}${Platform.pathSeparator}${submission.photoFileName}');

  /// Called only after the backend has confirmed the submission.
  Future<void> remove(String localId) async {
    final dir = await _dirFor(localId);
    if (await dir.exists()) await dir.delete(recursive: true);
  }
}
